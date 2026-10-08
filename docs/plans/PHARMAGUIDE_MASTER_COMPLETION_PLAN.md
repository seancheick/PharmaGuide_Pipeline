# PharmaGuide master completion plan

Updated October 8, 2026. Pipeline integrator: Codex. Original scope: Sean's accepted September 30 master plan. This document is the readable checklist; [LEDGER.md](../../scripts/audits/pending_items_20260926/LEDGER.md) remains the execution register, and the [ownership matrix](../../scripts/contracts/source_of_truth_matrix.json) defines production owners. Historical descriptions below do not override current code or approved decisions.

A checked implementation box means that specific deliverable is implemented, measured and independently reviewed where required. It does **not** mean the whole phase is finished or the catalog is released. Repository code pushed to GitHub and catalog publication are separate events.

## Current candidate checkpoint — October 8

Sean’s post-PR86 pipeline completed at 02:57:07 EDT: 38 datasets and 15,421 rows per stage. All 114 manifests and 174 owned files verify. The gated final catalog contains 15,244 products, 177 quarantines and all 73 BLOCKED products. The fresh clinical census covers 102,293 subjects: 15,420 products have complete determinations; one has two genuinely unresolved bile identities. No literature-review queue remains. The existing 132 verified interactions and 152 profile rules are paired without restamping their original build. Images: 15,208 reused, 27 downloaded, zero failures.

The comparison with the retained previous candidate covers all 15,244 shared products. Scores, tiers, quality-score statuses, safety statuses and flags are unchanged. Only 26 detail records change reviewed Evidence/assessment/confidence payloads; the other 15,218 are byte-identical. Ingredient ledgers, warnings and dose/banned owner payloads are unchanged. Daily Greens Plus 326161 moves from moderate to high assessment confidence because the existing confidence owner clears `evidence_review_incomplete`; this adds no efficacy credit. Receipts: final_previous_candidate_core_comparison.json and final_previous_candidate_blob_comparison.json.

App source 6eb0a4de passed the production reader for all 15,244 records, 27 connected screen cases, `make check` (3,755 tests; analysis clean) and 50 paired bundle checks. Its two source-grounded timing-canary corrections integrated through app PR 93 at origin b24b4b0c; the remote branch is deleted. Original user assets and the published interaction pin are restored. The packaging pin was local-only; remote publication parity is not claimed. The standard simulator destination failed on the ML Kit architecture restriction. A supported x86 build succeeded, and all four packaged artifacts match the frozen candidate. Launch still fails: the Intel host probe reports `Bad CPU type` and Rosetta is unavailable. Sean must complete Apple’s installer/license/password prompts. Zero actual simulator cases are accepted.

Sean explicitly authorized publication: “you can publish, im giving my authorization.” Do not ask again for that scope. Actual release gates remain mandatory. The original/live EDF baseline is unchanged; 38 unsigned safety exceptions persist: 25 milder summaries and 13 warning-bearing held products. No invented form grade, forged approval or policy bypass. The concrete decision packet is /Users/seancheick/pg_quality/post_pipeline_20261008/FINAL_SAFETY_DECISION_PACKET.md. The 401 deferred artifact/external full-profile nodes are running; 22,210 source passes and 16 declared skips are reused under exact fingerprints. Release, live and simulator acceptance remain open.

Candidate SHA/config/data provenance is frozen. Verified duplicate blob mirrors saved 2,508,643,950 bytes; completed simulator compilation caches saved another 1,121,280,000 bytes. The exact candidate, simulator package, original baseline and comparison evidence remain retained.

## Completion measure — October 8

**Main Phase 0–7 checklist: 64 of 70 boxes complete (91.4%).** Count only the eight phase sections under Updated execution checklist, including their nested deliverables; exclude historical checkpoint sections and repeated release reminders. This is an unweighted deliverable count, not an estimate of elapsed time, effort or release readiness. Repeated historical receipts are excluded from this completion measure.

| Phase | Complete / total |
|---|---:|
| 0 — Baseline and final freeze | 4 / 4 |
| 1 — Evidence/Dose separation | 10 / 10 |
| 2 — Identity and roles | 18 / 18 |
| 3 — Clinical Evidence coverage | 11 / 11 |
| 4 — Approved Dose policy | 6 / 6 |
| 5 — Numerical calibration | 6 / 6 |
| 6 — Flutter parity and nutrition | 4 / 6 |
| 7 — Candidate, approval and release | 5 / 9 |

Approved numerical policy, bounded calibration, the four live Evidence→Dose transfers and demonstrated identity/source-role corrections are integrated. Amla remains dormant/reference-only. PR72 adds aggregate preparation before brand processing; PR73 fixes shared individual-dose exposure; PR74 corrects a stale infrastructure assertion without changing production. The 193 prior catalog movements are source-attributed; the final 2,615-product correction replay has 608 explained numerical movements and zero protected safety/status/readiness/route changes. These are source and bounded-measurement results, not validation of a rebuilt release candidate.

Historical October6 independent pre-run clearance on main `a29eec4f` passed **all 19 checks**, with `completed=true`, `ready=true` and publication readiness still false: 21,973 source tests pass, 16 declared metadata exceptions remain, all 33 current raw canaries and all eight live verifiers pass, and final FDA freshness/input stability pass. Main CI37532345765 is green on that exact source; the earlier PR74 run37531185704 was cancelled, not passed. Sean's17:29attempt passed source tests but stopped on RxNorm timeout/DNS errors; the failed receipt is retained, and successful targeted retries and this complete clearance supersede its readiness result without restamping it. No newly reproduced production defect or runtime/data change was needed in this audit.

**Preserved artifact baseline — October 6, 22:45 EDT:** Sean's `batch_run_summary_20261006_204250.txt` completed Clean→Enrich→Score at 22:15 EDT on source `fe9963bd`. All 38 datasets contain 15,421 rows per stage; all 114 manifests and 174 owned-file checksums pass, and the then-current stage code/reference fingerprints had zero freshness issues. The launch preparation passes all 19 checks. The stored-output scoring snapshot owner now passes all 36 checks, including the five reviewed score changes that were stale before regeneration. The prior 070547 run and failed/interrupted launches remain historical receipts; they are not reasons to repeat the now-current corpus.

The existing candidate-only export chain completed successfully at 22:45 EDT. Local catalog `2026.10.07.024035` contains **15,150 products and 15,150 detail blobs**, with **271 contract quarantines, 73 BLOCKED products, zero export errors and zero contract failures**. Core SHA-256: `f6bc29768a76f46e3d09ef966d0f777a1693f20079e36f20663737339faa4b7a`. All candidate build gates pass, including source ownership, clinical drift, identity containment, assessment readiness, field completeness, form notes, stamped export contracts and catalog freshness. These checks do not establish a completed new Evidence census, movement acceptance, interaction rebuild, Flutter/device acceptance or release/full backstop.

Durable historical comparison receipts: `/Users/seancheick/pg_quality/post_pipeline_20261006/completed_preparation.json`, `pipeline_output_verification.json`, `catalog_validation_result.json` and `catalog_build.log`; candidate: `/Users/seancheick/pg_quality/post_pipeline_20261006/catalog_candidate/`. No live catalog was replaced, publication or phone installation performed. The baseline was reused for the remaining clinical, movement and app checks. Those checks reproduced output-changing source defects now collected in PR78; the baseline is diagnostic for that newer source. Sean completed that necessary Clean pass on October7 after PR78 integration; its fresh candidate and coverage receipts are recorded below. Monthly certification renewal remains active.

## Current pipeline validation and storage cleanup — October 7

Sean completed the necessary pipeline-only refresh: `batch_run_summary_20261007_081335.txt`, final dataset09:45:23EDT on integrated source `d8997816`. All19preparation checks pass, including22,087source tests/16declared metadata skips/401deferred nodes. All38datasets contain15,421rows perstage; all114manifests/174owned-file checksums verify and stage freshness has zero issues. The earlier failed preparation remains a failed historical receipt. No additional corpus is indicated.

The candidate-only catalog build passes every source/artifact gate. Candidate `2026.10.07.141113` contains15,146core rows/blobs,275contract quarantines,73BLOCKED products and zero export errors/contract failures; coreSHA `dff40db8d03ef8cc7e87ca56d26ba2e38b41a220a2a62cb9cfdebcf817af4d5b`. Existing interaction verification passes132/132 with zero warnings/errors; deterministic rebuild is byte-identical `8efb74ce74b2a46e834344d0feb8196bf1c3b59f743ff3d8db896d29ff9b6053` and the existing staging owner pairs it with this candidate. The original interaction build timestamp remains unchanged; the new verification receipt is separate.

**Clinical deliverable closure:** the full manifest-owned census covers15,421products/102,161subjects with no pending literature determination. Its only unresolved identities are two bile-material subjects on307560, both explicitly points-ineligible. Every reviewed519RAWproduct/5,869subject disposition and source row matches current outputs;436shared runtime/reference hashes are unchanged and five existing FDAauxiliaries match their previous qualification. Strict reachability covers all15,421products with zero errors/stale/unlinked/new matches. Q53's eight identity/applicability exceptions remain uncredited;264105/LA-5 remains a completed no-qualifying-evidence review. The individually source-verified44record batch, preparation/purpose limits and protected RAW/native controls now agree with the fresh artifacts. This closes the four remaining named Phase3 coverage/determination deliverables, without inventing identity, positive grades or benchmarks. It is not a universal new review of every legacy authority record:252baseline-triaged citation mismatches remain explicit clinical debt.

The2,249reviewed RAWcaptures match2,170included catalog products across six pillars and status;79honest `not_scored` captures remain excluded. Existing `shipped_whole_score` explains all1,920decimal-to-whole projections; no unexplained difference remains. Original/live baseline `edfdb110...` is preserved:15,109shared,37added,201removed,62unapproved safety exceptions. The October6comparison baseline has four additional identity holds removed in the fresh candidate; warning-bearing source holds232011/328450/314749 require explicit D25 disposition. All90current numeric movements are cause-reviewed:73covered by the accepted RAWcohort and17additional scored-artifact/source traces (14disclosure, two canonical preparations, one Olive Leaf Doseform). All17match current catalog projections; no new grade/benchmark/production fix. The all15,146shared-catalog protected-field comparison finds11explained changes:42Olive Leaf warnings restored, three omega citation-only updates, one standardizedform-context update with unchanged975mg decisions, and one false added-sugar warning removed because the label explicitly prints0gadded/1gtotal sugar. No unexplained shared safety/warning change; D25holds and original/live exceptions remain open. Ordinary score/tier movements remain cause-reviewed, not an individual approval queue. No publication is approved.

**Pipeline test acceptance:** release rung128passed/one skip, followed by the omitted interaction-orphan node passing after candidate pairing (0.27s); every release data/live gate passed. The full current collection exactly matches preparation's22,504nodes. Reuse22,103completed source nodes (22,087pass/16declared skips) and23fresh release-artifact nodes; the remaining full-profile378nodes (349artifact/29external) finished sequentially after release:346passed,29explicit external/OCR/submission opt-in skips and three artifact expectation failures. Allthree failed nodes now pass targeted tests-only repairs (102.80s);17named provider/projection/carrier/blend owner-consumer checks pass (71.82s). Source-grounded assertions retain canonical form/lineage, no chlorophyll Evidence borrowing and printed1160mgEPA+DHA/1450mgfish-oil concentration. Composed full-profile coverage is22,459passed/45declared skips, with initial failure receipts preserved; this is not a fresh22,504-node rerun. No new whole source rerun or corpus is required.

**Storage:** Sean explicitly authorized removal of redundant and obsolete generated artifacts. Verified duplicates, old September replay work trees, superseded stored-corpus freezes and older catalog payloads/assets were removed; originals, current corpus/candidate, required comparison DBs, current RAW/native captures, primary-source reviews, checksum manifests, compact reports, unique user assets/photos and unmerged work remain. Cleanup receipts identify retired paths; historical reports do not imply their retired working copies are still available. Disk increased from roughly6GiB to roughly148GiB free. The first census attempt unnecessarily copied~7.5GB before ENOSPC; its owned incomplete copy was removed and the successful census reads original hash-verified outputs directly. Future large work checks disk first and reuses existing outputs.

**Remaining scope:** eight Phase0–7 deliverables remain: final freeze, three Flutter/app deliverables and four expected-failure/decision/publication/live-verification deliverables. Production Flutter readers passed all15,146rows and20real-product screen cases. A retained old candidate path in the reused diagnostic template was caught by its SHA assertion and corrected; the affected20screen cases then passed, without changing production. Full app/bundle/physical phone acceptance is still open. Sean's local-install authorization remains valid, but his latest direction is to stay on the pipeline; no phone install was launched. Published interaction pinf5cb versus local8efb remains unresolved until authorized publication through its owner. Do not forge approvals, pins or green results. Complete remaining pipeline checks, resolve D25 and app prerequisites, freeze the exact validated candidate and obtain Sean's publication approval before the existing release chain and live parity checks.

Durable receipts: `/Users/seancheick/pg_quality/post_pipeline_20261007/` (`pipeline_output_verification.json`, `clinical_coverage_corroboration.json`, `q53_fresh_subject_checks.json`, `raw_measurement_catalog_parity.json`, `catalog_original_comparison.json`, `interactions/`, `release_backstop.log`, `full_backstop_coverage_plan.json`, storage cleanup receipts). Owner: existing master checklist/LEDGER, stage manifests, shared Evidence provider/resolver, export/catalog comparison, interaction staging and Flutter readers — evidence unchanged reviewed source/RAW subjects, fresh manifest-owned artifacts and named receipts. Will NOT create: another tracker, scorer/normalizer/registry/subject selector, public field/status, clinical/scoring policy or release bypass. This batch includes tests-only expectation corrections plus documentation/process: explicit failing nodes, source-grounded owner/consumer checks, full diff/reference/contradiction review and `git diff --check`. Production source/data/config remain unchanged; no new corpus is required for test/documentation edits.

## October 4 — catalog gate development policy

Implemented and independently reviewed in the existing catalog comparison owner: ordinary score/tier changes are report-only; safety weakening and warned-product removal retain exact reviewed exceptions. Historical comparison:3,046approval requests become43safety exceptions plus3,003visible quality movements; no flagged product or safety fact is lost. Focused owner/release-wiring checks60passed; independent gate checks48passed. Exact gate source3b0f10d6 passed all four CI shards (run37218555485) and was integrated on Sean’s instruction. This is gate implementation and historical measurement, not clinical acceptance or publication. Existing final candidate/app/clinical boxes remain open. Receipt and integration status: execution LEDGER.

## October 4 — audit integration and cleanup

- [x] Sean authorized integration; pipeline audit source/documents merged and pushed to main through fed96040, exact branchCI37215506742 green. App UL consumers merged and pushed to main3553342c, exactCI37214557986 green. Final runtime/data are identical to the independently reviewed27d9b751 source and passing103b699e local527/24declaredskip checkpoint; later pipeline commits changed only documentation.
- [x] Master/LEDGER integration states reconciled. Audit fixes are integrated, not release-validated or catalog-published. Main source changed after the frozen6ea851dc catalog; that candidate is now historical for these owners.
- [ ] Regenerate from Clean through Enrich and Score, rebuild catalog/interactions/app candidate, inspect measured changes and complete current release/bundle/device checks before exact-candidate publication approval. Do not restamp the old artifacts or publish them as this source.

Owner: existing UnitConverter/enricher RDA/UL and safety-explanation owner; Flutter existing shared ingredient readers/stack/DoseSafety; existing pipeline/release provenance. Will NOT create another scorer/converter/status/registry/tracker. The completed release branch was deleted after containment checks; automation was deleted and jobs stopped at Sean’s request.

## October 4 — exact-candidate verification

Historical locally built candidate: pipeline `6ea851dc`, catalog `2026.10.04.133540` (15,154 products), interaction DB `1.0.12` (132 records). Evidence directory: `/Users/seancheick/pg_quality/q53_release_20261003/final_candidate_6ea851dc/`.

- [x] Historical exact `6ea851dc` corpus: 38 stage chains / 114 owned, checksum-verified manifests; current input fingerprints; raw input inventory unchanged. Receipt SHA-256 `f3f5f90147025c0b3cecc484900933f7bd6f4205dff539a4d197eda6a2b102df`.
- [x] Historical exact `6ea851dc` clinical reachability: 15,421 products, zero findings. Receipt SHA-256 `54cc23059f3576f548afc880783abf4f6fd44dcc17f721c430fcf514bb3a2031`.
- [x] Preserve candidate hashes and original app baseline before local import; freeze the original movement report. Local import succeeds. This is development evidence, not publication approval.
- [x] Release backstop: 124 passed in 1,233.24s; strict owner/freshness/Flutter audits pass; citation audit has zero new mismatches or unresolved citations (252 known backlog mismatches remain reported). Receipt `test_release_after_import.log`.
- [x] Fix all38 reported full-backstop failure classes and integrate/push the test/docs batch (`bd824dc1`, `ffd5a44e`, `1b93c637`, `2e413434`, merged through `631c18df`). Focused verification:100 canaries passed plus both corrected remaining nodes passed;21 warning owner/consumer checks passed;all-row export parity passed in167.25s. No production scoring/data change from this batch, no replacement full-green receipt and no completed Flutter check claimed. Concurrent Vitamin E/safety runtime fixes are preserved; their new candidate remains pending.
- [ ] Complete full backstop and Flutter `make check` / `make verify-bundle`. Completed full run: 38 failed, 21,620 passed, 45 skipped in 3,502.87s. Sean stopped broad validation and requested a handoff; queued/running checks owned by this lane were stopped and the monitor was subsequently deleted. Test-only remediation addresses stale policy expectations, warning identity and an export-parity timeout; focused receipts are recorded in the LEDGER. No replacement full run or completed Flutter check is claimed.
- [x] Numerical census of all 3,046 distinct catalog-gate products saved in `catalog_movement_source_review.json`: 3,009 matched products and 37 removals. Largest absolute pillar movement is Evidence for 1,162, Formulation for 1,031, Transparency for 421, Dose for 358, Safety/Hygiene for 32, Verification for five. 2,335 move multiple pillars. This attribution does not establish clinical or human approval.
- [x] Representative canonical field-chain audit for DSLD 18529, 182730, 231868 and blocked 18924: printed label fields, amounts/units/DVs/order/panels preserved; scored→core shared rounding and blob provenance→core quality status/tier/safety agree. Receipt `canonical_field_chain_audit.json`; this does not establish device rendering.
- [ ] Finish actual device rendering audit. Launch reproduced simulator architecture incompatibility; no connected iPhone currently detected. Static field tracing does not close this box.
- [ ] Close human catalog movement review: 3,046 distinct flagged products (overlapping categories), including six milder safety statuses and 37 removed products previously showing caution. All 37 remain present in scored source as `not_scored` / `incomplete_product_data`, specifically `disclosed_form_unmapped`: declared preparation/form is unrecognized, despite full ingredient mapping and disclosed amounts. Independent review found 24 substance-risk markers, 30 UL signals and two high-dose caffeine signals (overlapping); none is currently blocked/banned/recalled, but removal hides existing cautions. This finding is not an approval to remove warnings. Preserve old baseline after candidate import; never regenerate the comparison against the candidate to erase this gate.
- [ ] Sean approves external catalog/interaction/Supabase/OTA publication after remaining evidence is complete. No such publication has occurred.


- [x] Integrate the reviewed preparation/source corrections, including removal of borrowed Mirtogenol→bilberry credit. Exact branch/main CI, local corpus checks and independent review passed; source is contained in main through `4e073a6b`.
- [x] Integrate structural-total Formulation correction `4f2a6509`. Failing-before regression; 121 focused checks; independent measured review; branch CI37181147593 and main CI37181628461 green; local527passed/24declared optional skips, skip guard green.
- [x] Regenerate and verify all38Clean/Enrich/Score chains/114manifests at `4f2a6509`; strict reachability covers15,421products with zero findings. These outputs are a verified historical candidate after later main changes, not final release proof.
- [x] Review/freeze the complete snapshot movement set against source and fresh artifacts: 18273085.8→86.1 and 28834477.2→78.4 change only Formulation (structural totals excluded); 20457146.9→62.5 changes only reviewed ingredient Evidence ownership. All three were independently accepted and generated through the existing freezer; the other33 snapshots are unchanged. Bounded36-label replay through newer main preserves displayed scores/statuses/safety;182730 raw Dose17.9039→17.9149 corrects declared choline below display rounding. Newest-source release validation remains required.
- [ ] Regenerate the newest merged runtime, complete local release, catalog/interaction/bundle parity, canonical field and real Flutter rendering audits, release/full backstops and exact-candidate publication approval. Main has subsequently merged safety-reason and declared-nutrient conversion corrections at `dd2769ad` (CI37183817363green); older artifacts cannot validate those changes.

Evidence: durable `/Users/seancheick/pg_quality/q53_release_20261003/final_candidate_4f2a6509/` and prior exact-source directories; existing execution LEDGER and authoritative worktree handoff. Owner: existing ingredient eligibility, scoring/export/display contracts. Will NOT create: another score/role owner, registry, status, tracker or approval shortcut. Nothing is externally published by this checkpoint.

## October 3 — master-plan state audit

This October 3 audit is historical; the October 4 checkpoint above is current. Older checkpoint prose below is retained as history; its unchecked boxes are corrected in place when later evidence closes the exact deliverable.

- [x] Reconcile every previously checked master-plan row against current source, named commits, local receipts and CI. All 34 cited commit references resolve in the pipeline or paired Flutter repository; all four relative receipt links and all 14 durable absolute receipt paths resolve. The six cited historical CI runs are green at their named SHAs. No checked deliverable required reopening.
- [x] Verify the current pipeline candidate: `main` and `origin/main` are identical at `5246ad20`; exact-source four-shard `pipeline-tests` run [37130043515](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37130043515) is green; the exact-source local corpus gate passed 527 tests with 24 declared opt-in skips and a green skip guard.
- [x] Correct stale historical plan state. D26/D24/omega ownership and magnitudes, the four retired Evidence amount safeguards, duplicate fiber judgments, alternate-serving reconciliation, all live numerical-rule ownership, all 35 historical Q3 crossings and bounded calibration are complete. The clinical source-research batch is complete; unresolved release-eligible determinations remain open and are not relabeled as completed clinical coverage.
- [x] Integrate the Q53/calibration lane and subsequent release-critical corrections into current `main`. The historical Q65 integration box is closed by containment through `5246ad20`; no active calibration branch is required for release.
- [x] Complete and inspect the fresh final corpus run from Clean. The accepted 12:39–13:41 EDT pipeline-only run completed 37 brand directories plus Product Submissions: 38 complete stage chains, 114 valid manifests, one shared reference fingerprint and one code fingerprint per stage, zero freshness/manifest/pipeline errors and zero new quarantined stale outputs. Cleaner holds remain explicit for labels `312659` and `250356`, whose raw records contain no active ingredient rows; they are not converted into scored products. The detached 12:35 attempt remains rejected.
- [ ] After the corpus succeeds, run strict reachability, catalog/interaction/Flutter build and rendering checks, sequential release/full backstops, freeze the exact manifest, obtain publication approval, publish and verify live parity.

Current completion boundary: scoring policy, scoring implementation and bounded numerical calibration are done. Remaining source work is the explicitly unresolved clinical-determination queue plus the broader active/excipient source-section audit and final Evidence-subject census. Nutrition Facts, active ingredients and other ingredients retain one canonical pipeline partition; final acceptance requires real rebuilt-artifact and Flutter rendering verification.

Owner: this plan for readable phase state; `scripts/audits/pending_items_20260926/LEDGER.md` for the execution register; `scripts/contracts/source_of_truth_matrix.json` and existing production owners for behavior. Evidence: current source containment, commit/receipt census, exact-source CI, local gate and frozen replay receipts. Will NOT create: another plan, tracker, scorer, registry, role classifier, public field/status or app calculation.

## October 2 — whole clinical batch and Dose decision packets

This is the historical October 2 clinical checkpoint; the October 3 audit above is current. Baseline: `753aa5cf`. Fixes: `1d62acbb`, `51595506`, and the historical curation-rerun correction `59d96720`. Bounded research and factual fixes were completed here; later sections close the approved scoring policy and calibration while release remains separate.

- [x] Review all nine Q53 labels and unresolved subjects together. Live NIH ingredient rows, servings and statements match retained raw for all nine. Preserve insufficient strain/preparation identity; do not guess a match or a positive grade.
- [x] Complete the eight-family source comparison: PHGG, inulin/FOS, XOS, GOS, phage, Seed, IS-2 and LactoSpore. Distinguish preparation, population, outcomes, replication and commercial involvement. This is bounded research, not a systematic review or clinician signoff.
- [x] Correct six existing curated entries: LA-5 source scope and review attribution; MTCC5856 design, regimen and limitations; IS-2 comparator/outcomes; LactoSpore’s unsupported immune tag; oat-bran beta-glucan basis; and FOS response specificity. Existing clinical grades, benefits, thresholds, signoffs and context approvals remain unchanged.
- [x] Fix ALCAR’s reference at the existing adequacy producer. All 27 aliases retain the acetylated form without borrowing L-carnitine’s 500 mg reference. Free-carnitine controls remain valid. No new benchmark or magnitude.
- [x] Fix awarded-citation provenance at the existing Evidence owner. Shared assessments award no Evidence and initialize an empty scoring-citation list; the credited native family supplies citations. IS-2 cites IBS trial `31434935`, not athlete trial `35249118`. Research inventory remains intact.
- [x] Deliver the whole generic/omega Dose packet: nine groups, four D26 safeguards, one-to-four-purpose missing-benchmark/form/amount cases, excess versus Safety, and omega alternatives. It contains 86 synthetic boundary probes and 16 fresh real-label probes at the baseline. Its ALCAR scores predate the correction.
- [x] Complete failing regressions, owner checks and independent review: 616 owner/consumer tests; 46 citation matches with no mismatches; independent alias, source and adversarial family checks.
- [x] Complete the 344-label frozen-raw replay and independent classification of all 150 changed captures. Public changes: 51 Dose-only movements, including 50 decreases and one 0.4 increase; 25 quality-tier downgrades and no upgrades. Safety, status and route stay unchanged. All movements are explained.
- [x] Pass the local corpus/artifact gate: 527 passed, 24 declared opt-in skips, passing skip guard. Earlier missing-mount attempts were refused and excluded. This does not validate release freshness.
- [x] Repair the stale Wave 2 authoring facts found by CI. Exact rerun, identity, source and status guards remain; all 59 contexts verify without writing, and three deliberate factual mutations are rejected. Runtime scoring/data fingerprints remain identical to the accepted replay.
- [x] Complete exact-source `59d96720` CI: [run37074275969](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37074275969), 18,237 passed, 183 declared skips, all four shards green. The earlier fixture-failing run is superseded.
- [x] Integrate the reviewed source and documentation with current main through the active integrator. The completed candidate is on `main` at `2090d2b3`; post-push run 37095846472 passed all four CI shards.
- [x] Decide and implement the approved D26/D24/omega policy through existing owners; complete bounded calibration, independent review and the 344-label frozen replay (`aca66621`; [receipt](../../scripts/audits/q53_d26_calibration_20261002/README.md)).
- [x] Pass exact-source four-shard CI at `aca66621`: 18,717 passed / 183 declared skips, all skip guards green ([run37091524920](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37091524920)). The two preceding failed runs are superseded by the complete correction batch.
- [x] Close the remaining alternate-serving duplicate class and every live numerical-rule ownership row. The 15,414-label raw census has zero repeated top-level names after reconciliation. Recover and inspect all 35 historical Q3 quality crossings individually; all are quality-tier aliases with unchanged Safety/Hygiene and B1.
- [x] After final integration, Sean ran fresh Clean/Enrich/Score from `main` across all 38 datasets (`scripts/products/reports/batch_run_summary_20261003_003215.txt`). All 38 stage chains completed with consistent reference/code fingerprints. The local corpus gate passed: 527 passed, 24 declared opt-in skips, skip guard green. Three initial failures were one stale cross-module assertion; the accepted `232295` Evidence-floor movement reproduced exactly, and the corrected ownership assertion passed 12 focused checks before the green combined rerun.
- [x] Audit the first local release-build attempt. Its snapshot gate stopped promotion and exposed one real explanation defect: held omega product `74716` had zero Evidence credit but inherited `evaluated_applicable` from generic metadata. The omega owner now emits the canonical state (`identity_material_unresolved` or `applicability_unestablished`), and the public pillar no longer claims limited applicable evidence. The approved material scoring changes are versioned as engine `4.5.0`; omega raw-module canaries were re-pinned to the already-measured policy. Focused omega checks: 98 passed; local gate after the source fixes: 527 passed / 24 declared skips.
- [x] Re-run Score only across all 38 fresh enriched datasets from corrected source `18bfdcfb`. All 38 manifests are complete and share one reference fingerprint and one scoring-code fingerprint; all 15,421 artifacts report engine `4.5.0`. Freeze the four approved numerical movers plus carrier-mass-only control `12043`, whose score remains 27.7 while assessment becomes correctly partial. Snapshot gate36passed; local gate527passed/24declared skips.
- [x] Audit the next local release attempt through the strict clinical-match reachability gate. The gate found 137 enriched artifacts whose stamped matches differed from replay because Evidence ran before final taxonomy/route roles. Fix the existing enrichment order and shared probiotic identity role: the aggregate CFU projection owns dose while every declared strain remains a purpose owner. Fail-first ordering and NP-strain role regressions now pass. Frozen raw replay of all137affected labels plus35controls is clean on fresh enrichment;10scores increase through Evidence only,4move Poor→Needs improvement, and no score decreases, non-Evidence pillar, route, scoring-status or safety movement occurs. All35controls keep their scores; one carries role-provenance metadata only. Focused owner/consumer slice:546passed. Existing generated corpus remains stale for this source correction.
- [ ] Rebuild and inspect the catalog, interactions and Flutter bundle; run the release/full backstops, freeze the exact manifest, obtain publication approval and verify live parity.

Owner: existing clinical registries and IQM; `RDAULCalculator::_form_scoped_reference`; `studied_formulas::assess_probiotic_evidence`; and `probiotic_evidence::score_evidence` with its existing eligibility/family selector. Evidence: source regressions, primary receipts, consumer searches and independent production probes. Will NOT create: another registry, scorer, parser, public field/status, grade, benchmark or numerical policy.

The completed source comparison is in [research.md](../../scripts/audits/pending_items_20260926/research.md). The [existing transfer packet](../../scripts/audits/evidence_dose_transfer_20260930/README.md#october-2-whole-remaining-dose-decision-packet) now contains the whole remaining Dose decision packet. Durable receipts: `/Users/seancheick/pg_quality/clinical_completion_batch_20261002/`. All nine Q53 labels still have incomplete Evidence readiness; overall assessment-complete does not mean clinical review is complete.

## October 2 — probiotic/prebiotic ranking corrections (Q59)

**Closed for input-integrity remediation and bounded validation.** This closure does not establish completed clinical coverage, calibration, market-wide ranking eligibility or release readiness.

- [x] Reproduce the ranking audit against main `77cb8993`, inspect raw labels and official label images, and classify the findings before changing owners.
- [x] Preserve PreticX/XOS as the declared preparation and parent amount; remove the erroneous generic complex alias. True blends and nutrition carriers remain distinct.
- [x] Resolve Nutricost's single declared chicory/inulin preparation through the existing cleaner and identity contract. Preserve source membership and forms; reject partial preparations, unrelated botanical companions and nested blends.
- [x] Stop generic cranberry/PAC names from inheriting a 25% PAC form. Keep explicit concentrations, whole powder, juice and marker provenance distinct. Correct singular/plural marker recognition at the existing descriptor owner.
- [x] Correct exact DSLD294036's printed 1.2g unit using the existing reviewed correction register. Apply combined value/unit corrections to the matching original serving column only; protect other columns and earlier corrections.
- [x] Route genuine digestive-enzyme hybrids using the existing shared feature vector. Explicit probiotic products keep their probiotic route.
- [x] Send non-fiber purpose ingredients to existing generic Dose; neither a prebiotic marketing title nor incidental nutrition fiber supplies a fiber amount or a new clinical benchmark.
- [x] Refresh existing ConsumerLab records through the canonical source parser. Historical certification earns no current credit; a fresh, sourced completed absence remains scoreable, while incomplete/stale provenance remains held.
- [x] Freeze and replay final production source `b8d298ac` across **1,544 unique products**:887 primary labels,604 expanded cranberry/chicory controls,51 prior correction controls and2 manual submissions. All captures succeed with unchanged source/input provenance;23 score movements and2 route movements are explained. No scoring-status or safety-gate movements;51 correction controls and both manual submissions are unchanged.
- [x] Complete exact-source four-shard CI ([run37054020556](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37054020556)): **18,213 passed/183 approved skips**, all shards green. Local corpus/artifact gate: **527 passed/24 approved opt-in skips**, skip guard passed. Fresh final measured review accepted `b8d298ac`.
- [x] Integrate and push the reviewed source/documentation batch through main `95af59fd`; production fingerprint matches tested/measured `b8d298ac`. Twenty final public artifacts retain typed safety and emit no new POOR compatibility verdict. Runtime publication remains pending.
- [x] Complete the planned eight-family preparation-specific source research and bounded numerical calibration. This closes the approved scoring/calibration work, not every unresolved positive/negative clinical determination or release acceptance.
- [ ] Complete the remaining release-eligible clinical determinations and identity holds named in Phase 3; insufficient identity may remain a justified hold.

- [x] Preserve separate regression and current-state ranking artifacts. `current_state_ranking.md/.json` ranks all1,544 measured inputs using existing route outputs, the prior prebiotic/inulin title subset and canonical catalog brand identity. Ora leaves the probiotic group; Nutricost becomes second in the measured prebiotic group. This is a bounded diagnostic census, not exhaustive market coverage or a publishable recommendation.
- [x] Produce before→after six-pillar breakdowns for the five requested movers plus Ora, historical certification, Seed and PHGG. `major_mover_breakdowns.md/.json` retain production reasons and source hashes; no score rule changed.
- [x] Map generalized preparation/amount/concentration/certification/hybrid/safety invariants to existing executable regressions and bounded replay receipts (`invariant_and_ranking_gate_review.md`). Exact product scores are supplementary, not permanent calibration targets.
- [ ] **Consumer ranking publication gate:** establish valid canonical route/primary intervention, justified comparison purpose/population, no unresolved structural defects, completed clinical applicability, approved Dose/calibration, current sourced certification and exact fresh candidate/release provenance. Use existing owners and review receipts; do not add `ranking_eligible`, a comparison registry or another classifier without an approved contract. A scored product need not belong in every comparison.

Continue structural repairs only for reproduced defects. Surprising scores first require input/driver inspection; correct inputs then go to clinical review/policy/calibration. Do not force Seed above PHGG or lower Nutricost to fit brand intuition. Thorne's improvement is existing generic Dose within the unchanged digestive route;527 checks were the local corpus/artifact rung, not a new focused suite.

Owner: `enhanced_normalizer.py::EnhancedDSLDNormalizer` (nutrition and single declared source form), `identity_integrity.py::resolve_identity`, `enrich_supplements_v3.py::_is_source_descriptor_form`, `scoring_input_contract.py::_route_is_probiotic_class`, `fiber_digestive_dose.py::score_dose`, `cert_resolver.py::_record_to_resolution`, existing verification assessment and existing label-correction register/applier. Evidence: fail-first production-boundary regressions, existing matrix/callers, official raw-label trace, final frozen replay and source reviews. Will NOT create: another scorer, normalizer, form parser, registry, route list, public field/status, benchmark or numerical policy.

Representative corrections: Nutricost inulin71.5→87.1; Pure capsules38.0→61.5; exact cranberry label48.7→60.1; Thorne38.2→51.0 through existing Dose credit, without a new phage benchmark; two Nature's Way historical-certification products83→78. Seed's preserved manual result remains84.5. Quality movements are not safety movements. The additional14 score decreases remove unsupported cranberry form/quality credit; they are not new deductions.

Receipts: `/Users/seancheick/pg_quality/pro_prebiotic_rank_audit_20261002/`: final `*_complete.jsonl` plus metadata, four `*delta_complete.json` comparisons, official294036/306369 label images, canonical ConsumerLab receipt and `clinical_calibration_packet.md`. Earlier draft holds and near-final measurements are superseded.

**Clinical-review sequence — October4 bounded reviews completed; broader census exceptions remain open:**

1. [x] PHGG/Sunfiber: exact preparation and population/outcome applicability, clinical certainty/replication and why the current raw18/reference18 becomes Evidence20/20. Studied amount matching is assessed by existing Dose, not charged again in Evidence.
2. [x] Inulin/FOS: exact preparation/source mapping and applicability for Nutricost, Jarrow and BulkSupplements; audit the current15.6 Evidence credit against verified interventions and endpoints.
3. [x] XOS/PreticX: preparation versus active-equivalent identity, generic versus branded evidence, clinically meaningful versus microbiome endpoints and existing Dose benchmark wiring.
4. [x] GOS: inspect GNC's low-end comparator and its actual preparation/intervention; unresolved research is not proof of no efficacy.
5. [x] PreforPro/bacteriophage: exact marketed intervention, standalone versus combination attribution, patient outcomes versus microbiome endpoints and studied-dose applicability.
6. [ ] Probiotic strain/formula families: exact strains versus species records, blend/formula applicability, population/outcomes, replication/independent confirmation and sponsorship provenance. Total CFU never becomes a per-strain dose. Include Seed and the currently credited IS-2/LactoSpore families.

October4 source review supersedes the frozen PHGG/inulin/Spirulina direction assumptions: selective positive/null outcomes now use the existing mixed classification; phage/FOS human research is retained without unsupported affirmative credit. Trial amounts remain Dose facts, and exact retail/trial preparation equivalence remains limited where not verified. Review funding descriptively under existing policy; no new sponsor penalty, benchmark or calibration magnitude. The source census and measurement receipt below distinguish completed bounded reviews from broader unresolved subject/identity exceptions.

Freeze Q59 normalization/identity/routing work unless another defect is reproduced. This is not a prohibition on correcting already tracked ownership defects or release-critical bugs; those need their existing fail-first/measurement gates. Seed's14.5 versus IS-2's16 comes from recorded outcome grading under current policy, not a funding deduction; PHGG's raw18/reference18 becomes public20. No new benchmark, positive clinical determination or magnitude was silently added. The later approved batch closes D26/D24/omega and bounded calibration. Q53 clinical holds, broader role/source work, the fresh Clean corpus, exact candidate approval and release verification remain.

## PHGG/Sunfiber clinical-source checkpoint — October2

- [x] Verify both indexed papers by full primary text and live PMID content/title:26855665 (Niv2016),31509971 (Yasukawa2019). Both explicitly used Sunfiber; earlier prose denying the brand link was wrong.
- [x] Correct only existing `BRAND_SUNFIBER`: author/date, randomized enrollment121+44=165 (with analyzed populations distinguished), explicit brand attribution, narrow positive/null outcomes and commercial-support limitations. Remove uncited meta-analysis/immune/stress/SCFA efficacy claims and the unqualified GuarFiber alias; do not infer a hydrolyzed preparation from native guar wording.
- [x] Write four fail-first clinical-record regressions; all initially failed, then passed. Entry/data-batch checks216passed; relevant clinical/Evidence owner slice177passed. Canonical batch check:one entry,zero problems. Both live citations have exact-title/topic matches.
- [x] Freeze41real labels:33full staging text-census matches plus8controls. All scored captures remain identical. All five existing enriched Sunfiber matches are covered. A separate copied-raw control with Sunfiber form/notes removed changes89→75, Evidence20→6only, with unchanged status/Safety; this is a synthetic defect demonstration, not a shipped product delta.
- [x] Complete exact-source gates at `77137e6f`: four-shard CI [37062220801](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37062220801), **18,217 passed / 183 approved skips / zero failures**; local **527 passed / 24 approved opt-in skips**; fresh measured review accepted. Source integrated with the accompanying plan receipt; runtime release remains separate.
- [ ] Close remaining PHGG clinical/Dose applicability determinations: prospectively registered outcome hierarchy where available, population-specific studied-preparation exposure and generic-versus-branded applicability. Cross-family numerical calibration is complete; Positive_strong/tier1 remains a frozen existing clinical-policy baseline, explicitly not re-ratified by this factual correction.

Why227960 still has Evidence20: existing brand+multiple-RCT+positive_strong policy supplies a decisive raw18 floor, normalized at the fiber route's18 reference. Its additive clinical pipeline component is7.92. This is the actual owner chain, not independent-confirmation or whole-retail-formula proof. The label declares3.2gSunfiber preparation per serving ×2daily=6.4g/day; indexed trials used6g/day after titration for IBS bloating and5g/day for loose-stool form. Preparation grams differ from dietary-fiber assay grams. No new studied-dose benchmark, amount gate, score magnitude or sponsorship deduction is introduced.

Owner: `backed_clinical_studies.json::BRAND_SUNFIBER`; existing enrichment clinical matcher/applicability, `generic_evidence::_primary_mass_floor`, existing fiber/generic Dose and scored artifact. Evidence: indexed primary papers, raw227960, canonical batch/citation tools, fail-first tests, frozen comparisons and independent review. Will NOT create: second registry/scorer/parser, public field/status, benchmark or numerical policy. Receipts: `/Users/seancheick/pg_quality/phgg_clinical_review_20261002/`. The later approved batch closes D26/D24/omega and numerical calibration; the PHGG clinical determinations and release obligations above remain open.

## Inulin/FOS factual-source checkpoint — October 2

- [x] Verify all three indexed PMID titles/content (35833477,34555168,38309832), healthy-adult review full text and FDA inulin UNII JOS53KRJ01. Generic “prebiotic fiber” does not establish inulin; FOS remains within the reviewed ITF family, without chemical or outcome equivalence claims.
- [x] Correct existing `INGR_INULIN`: remove the overbroad alias, unrelated stress/muscle-recovery tags and untraceable automated420/224 discovery counts; distinguish surrogate microbiome results, healthy-subject bowel benefits, mixed preparation-specific calcium outcomes and low/very-low-certainty cardiometabolic risk factors. Do not sum overlapping review populations or create a benchmark.
- [x] Four fail-first regressions;381 affected entry/batch/applicability/Evidence checks passed. Fresh review reproduced calcium-outcome conflation; fixed it and four final focused checks passed. Existing direction/tier/confidence retained as the pending calibration baseline, not re-ratified.
- [x] Final238-label raw comparison: zero full scored-payload deltas; all132existing enriched matches covered. Baseline220 plus disjoint18 retain identical source and verified raw hashes. Nutricost87.1, Jarrow77.4, BulkSupplements73.1 and all15.6 Evidence results unchanged.
- [x] Independent source/measurement review accepted; local527passed/24approved opt-in skips with passing skip guard.
- [x] Final four-shard CI at`0bbcedc5` [37064447723](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37064447723): **18,221passed/183approved skips/zero failures**; source integrated with this accompanying plan receipt. No runtime publication.
- [ ] Complete remaining preparation-specific clinical-certainty and Dose-applicability determinations; inaccessible full-text details, endpoint heterogeneity and precise funding roles remain explicit research limits. Numerical calibration is complete; this factual checkpoint does not close the clinical phase or ratify15.6 Evidence.

Owner: `backed_clinical_studies.json::INGR_INULIN`, `SupplementEnricherV3::_clinical_study_match`, existing clinical applicability, generic Evidence and route Dose. Evidence: indexed primary content, schema optional-count semantics, canonical batch check, production matcher regressions and frozen-label receipts. Will NOT create: registry/scorer/parser/public fields/status/benchmark/numerical policy. Baseline91884042; final source0bbcedc5. Receipts: `/Users/seancheick/pg_quality/inulin_clinical_review_20261002/`. The later approved batch closes D26/D24/omega, serving reconciliation and numerical calibration; inulin/PHGG clinical determinations, broader roles and the final corpus remain open.

## XOS/PreticX source/preparation checkpoint — October 2

- [x] Verify PMID24513849 and26300782 by live title/content; retrieve open2015primary full text and indexed2014publisher methods/results.2015authors distinguish nominal2gXOS from2.8g70%preparation. Do not transplant that purity to2014or currentPreticX labels.
- [x] Correct only existing IQM XOS notes: remove universal comparative low-dose efficacy wording; distinguish microbiome/tolerability outcomes from symptom relief and metabolic benefit.2014Table3low-dose versus placebo week-eightP=.052 differs from stronger prose. Neither retrieved study namesPreticX brand/grade; supplier continuity is not proof of equivalence.
- [x] One actual fail-first source-copy regression;241focused preparation/batch checks pass. Canonical one-parent patch0problems, only XOS notes differ inside parent. Changed-parent citation check4MATCH/0mismatch includes two unchanged sibling citations.15raw captures (six XOS matches plus nine controls) remain identical; Pure capsules61.5 and powder60.1 retain Evidence0/Dose7.2.
- [x] Fresh source/measurement review accepted. Both snapshots and all15raw/output hashes checked;436committed source hashes verified. Five ignored FDAassets occur only in baseline manifest: do not claim full environment equivalence or release validation.
- [x] Exact-source97cbff88 four-shard CI [37066989036](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37066989036): **18,222passed/183approved skips/zero failures**; local **527passed/24approved opt-in skips**, skip guard passed. Source integrated with this accompanying plan receipt; no runtime publication.
- [ ] Close preparation-specific clinical-credit and Dose determinations:2014purity, explicitPreticX linkage, endpoint eligibility/clinical grading and studied-exposure applicability remain open. Published microbial research is not “no human research”; unchanged0Evidence is not a completed negative clinical review.

Owner: `ingredient_quality_map.json::prebiotics.forms.xylooligosaccharides (XOS).notes`; existing prebiotic identity/preparation, backed clinical matcher/applicability and exposure/fiber Dose. Evidence: canonical matrix/schema, raw label rows, live citations and primary text,15-label frozen replay. Will NOT create: registry/scorer/parser/publicfield/status/benchmark/numerical policy. Baseline5938d487; source97cbff88. Receipts: `/Users/seancheick/pg_quality/xos_clinical_review_20261002/`. Existing fiber Dose mass table supplies current credit; it is not established XOS-specific trial adequacy. Numerical policy is now calibrated, but XOS-specific clinical/preparation applicability remains open before release.

## Execution discipline — October 2

- [x] Align shared, scoring-change, clinical-data, curated-data and FDA-sync instructions around surgical iteration:
  failing node → defect-class edge cases → relevant owner/consumer checks → bounded measurement
  and required review → one integrator-owned combined checkpoint. A checkpoint failure returns
  to targeted fixes; it does not trigger a whole-suite run after each repair.
- [x] Require each agent to resume from the current handoff and relevant plan/LEDGER items,
  record owned files and evidence, and check off only the deliverable actually demonstrated.

Owner: `AGENTS.md::Tests` defines the shared execution rule; existing scoring/clinical
instructions reference it. This plan remains the readable checklist and LEDGER the execution
register. Evidence: reviewed the conflicting keyword-only and per-commit test instructions,
aligned their text, and checked the documentation diff. Will NOT create: another runner,
profile manifest, tracker, scoring owner or release shortcut.

These documentation changes do not validate automated scheduling or CI, complete a scoring
phase, or replace the remaining corpus/release gates.

## October 2 — CI and CFU audit checkpoint

- [x] Preserve Claude's four-shard CI and real Flutter-repository checks, with one canonical test-profile manifest.
- [x] Correct machine-wide scheduling: focused fast file/node checks bypass the queue; broad fast/local runs share bounded one-worker slots; full/release/slow remain exclusive. Child workloads retain lock lifetime, including worker slots.
- [x] Reject unrelated skips even inside declared files; the local rung rejects absent corpus/build/raw inputs. Real local gate: **527 passed / 24 declared opt-in skips**.
- [x] Execute Linux print geometry/render tests with installed fonts instead of excusing them through a platform skip.
- [x] Independently reproduce and correct CFU prefix, liquid, daily exposure, unknown-unit and warranty ownership defects at the existing enrichment/serving owners. Preserve physical equivalents printed in the selected panel notes; product-name prose is not a serving basis. CFU combined focused gate: **151 passed / one declared OCR opt-in skip**; final harness/memory gate: **24 passed**; fresh review: **248 converter cases and 20 full-enrichment cases passed**.
- [x] Freeze the final 455-label replay: nine explained changes, 446 unchanged; six totals decrease 0.8–1.0, three CFU metadata changes only. No tier, route, status or Safety changes.
- [x] Integrate and independently validate the normalizer instance-cache memory fix; 16 frozen production controls remain byte-equivalent.
- [x] Pass exact-source four-shard CI at `31f41e56` (run 37033681364).
- [x] Pass final exact-source four-shard CI at `913fc9fe` ([run 37036894025](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37036894025)); integrate/push to main and remove equivalent branches/worktrees. Recovery tags and ignored handoff copies are preserved.

Owner: `SupplementEnricherV3::_collect_probiotic_data`, `_statement_cfu_per_serving`, `_extract_guarantee_type`, existing serving-unit/selection helpers; `scripts/test.sh`, `test_profiles.py`, `test_lock.py`, `ci_skip_guard.py` own validation. Evidence: fail-first probes, production-boundary regressions, frozen raw replay and independent review. Will NOT create: another count/parser/serving owner, scorer, public field/status, scoring policy or test manifest. Earlier rejected measurements are not acceptance evidence.

Historical next batch was **D26**. The later approved implementation supplies equivalent existing Dose ownership for the named groups and closes D24/omega numerical policy and calibration. Broader active/excipient roles, clinical coverage, the fresh corpus, exact manifest approval and runtime publication remain later gates.

The unrelated DEA-date review is **Q56**, not Q54: Q54 already identifies the integrated CFU consolidation. No clinical record was changed in this infrastructure/CFU batch.

## Earlier validated scoring checkpoint

Earlier validated pipeline source was `b7eeb178`: the October 2 post-pipeline
owner corrections. Final fast: **18,101 passed, 168 skipped, zero failures or
expected failures** (976.12s). Independent review accepts all 24 score changes
across 1,496 frozen raw labels; 46 public controls and 33 canaries preserve their
accepted results. Source integrated and pushed on main through `54a374cb`.
App source remains `63eeabff`; this batch changes no app code or public fields.
Sean's run of 38 datasets and 15,421 products validates its `fa8c50bc` baseline and the
previous CFU/Transparency repairs, but its outputs are stale for the corrected
source. Numerical calibration later closed; final corpus/catalog/runtime acceptance remains open.
Earlier source gates are historical receipts, not release approval.

- [x] Reconcile current main and the integration lane, including the release/storage changes on `d021061b`.
- [x] Integrate and push the approved probiotic production model and Ravage correction to pipeline `main` (`0f695b19`; Q47/Q48); source and plan subsequently pushed through `3ee91eae`.
- [x] Match the approved probiotic candidate across 1,259 frozen labels: 542 probiotics and 717 controls; no numerical/component/tier/route/status/Safety/confidence mismatch.
- [x] Close Ravage's cinnamon expected failure with a cleaner-owned fix, not a scorer exception.
- [x] Complete the earlier integrated source checkpoint: **17,915 passed, 167 skipped, zero expected failures** at `3ee91eae`, with independent review. Artifact-dependent skips still require release-stage checks.
- [x] Complete the remaining prominence and alternate-serving corrections covered by the approved D26/Q39 batch, including the zero-repeat top-level raw census.
- [ ] Complete the broader dual-use active/excipient source-section audit and final subject census; completed Ravage and trace-protein cases are bounded examples.
- [ ] Validate a fresh complete catalog, approve its exact manifest, publish and verify live behavior.

No catalog release has occurred under this plan. Recorded checkpoints validate their named source and frozen samples, not the entire rebuilt corpus. The earlier combined source was pushed through `19d4f661` (tested production checkpoint `a3a2d904`). Q49 and Q51 remain separate integrated items. Q53 source correction `0acde33e`, its two benchmark follow-ups and Q52 source correction `6a15be14` are integrated on main. Final combined fast: **18,008 passed,168 skipped,zero failures/xfails**; source fingerprints match measured candidate bytes and fresh review accepted. D26 was later closed; remaining identity/research cases and fresh candidate validation remain open. Source push and cleanup receipts are recorded below.

## Phase 0–2 completion and remaining artifact gates

The October 5 accepted source receipts reconcile these boxes against current production. An unchecked box means a real outstanding deliverable or an explicitly named later gate; it is not permission to skip it.

| Item | Current status | What happens next |
|---|---|---|
| Phase 0 final baseline/artifact recheck | Current source reconciliation complete; final gate pending | Repeat at the exact candidate freeze, after the last scoring/data change |
| Phase 1 generic amount transfer / D26 | Implemented, measured and independently reviewed | Validate on Sean's fresh full corpus before release |
| Phase 1 omega Evidence mapping | Implemented with applicability holds | Validate all eight classes on the fresh full corpus |
| Phase 1 transfer-invariant audit | Four live scopes transferred,183 frozen labels measured and reviewed; no new positive Dose benchmark | Validate fresh full-corpus output; Amla reference-only scope remains dormant |
| Phase 2 shared prominence owner | Implemented, measured, reviewed and integrated | Marked complete; retained amount guards stay under Phase 1/D26 |
| Phase 2 remaining serving duplicates | Closed for current raw corpus | Recheck canonical output and app rendering after fresh Clean |
| Phase 2 dual-use ingredient roles | Shared amount-based excipient demotion corrected; all demonstrated affected labels replayed | Final artifact validation uses the corrected source owner |
| Phase 2 accepted October4 subject census | Complete then:15,421labels/102,281subjects;340pending subjects retained; current-candidate counts await rebuild | Corroborated source contradictions are closed; retain unresolved clinical/preparation holds and measure current coverage after rebuild |

**Next candidate work:** the approved four transfers, clove/source defects and final shared identity/activity batch are implemented, measured, reviewed and validated. Sean completed the204250 Clean→Enrich→Score run and the local catalog candidate passes its build gates. Continue fresh census/movement/interaction/app/release validation from those same outputs; do not schedule another corpus without a reproduced output-changing fix or invalid provenance. Exact preparation/route/purpose clinical holds remain visible in the existing research/LEDGER; they do not become blanket negative or positive determinations.

## Fixed boundaries and Owner Check

| Decision | Existing production owner | Evidence |
|---|---|---|
| Shared purpose/prominence roles | `scripts/scoring_input_contract.py::classify_ingredient_roles` | Shared owner/consumer defects validated; final artifact/app checks remain under Phases 6–7 |
| Evidence subject set | `scripts/scoring_input_contract.py::get_evidence_subject_rows` | Matrix, ownership tests and production consumers |
| Raw source sections, label provenance and normalization | `scripts/enhanced_normalizer.py::EnhancedDSLDNormalizer.normalize_product` | Raw JSON replays and source/label-ledger tests |
| Amount/exposure adequacy | Existing `row_exposure`, `rda_ul_data.adequacy_results` and route Dose modules | All-route transfer inventory and exposure tests |
| Probiotic Evidence | `scripts/scoring_v4/modules/probiotic_evidence.py::score_evidence` | Q47, exact frozen equivalence and reviewed regressions |
| Public score/export | `scripts/score_supplements_v4.py::score_product_v4` → `scripts/scoring_v4/scored_artifact.py::build_scored_artifact` | Production/export contracts |
| Generated interaction DB | `scripts/build_interaction_db.py::main` | Checked source inputs and Q42 regeneration receipt |
| Nutrition | Existing cleaner display ledger, detail-blob export and Flutter nutrition reader | Pipeline regressions and real-product simulator receipts |

**Will NOT create:** another scorer, normalizer, prominence classifier, Evidence subject list, post-route Dose engine, clinical registry, brand resolver or app-side product-quality calculation. Preserve the pillar maxima **20 / 20 / 20 / 15 / 15 / 10**, public statuses, score fields and compatibility mirrors.

## Updated execution checklist

### Phase 0 — Baseline, branches and inputs

- [x] Establish the reconciled baseline and preserve the rejected Dose draft as historical decision material.
- [x] Confirm the missing interaction SQLite file is generated output; verify curated inputs before rebuilding with its canonical builder (Q42).
- [x] Record focused/frozen replay provenance and current worktree ownership.
- [x] **FINAL-CANDIDATE GATE:** October8 exact candidate frozen after image backfill: core998f3611, interaction5df294e4, detail index/export manifests and2,262 runtime/config/data hashes recorded. All114 stage manifests/174owned inputs verify with zero freshness issues; original baseline and surviving worktrees recorded. This closes the freeze/provenance deliverable, not simulator, safety decisions or publication. Receipt: final_candidate_freeze_pending_validation.json.

### Phase 1 — Evidence → Dose separation

- [x] Produce the all-route ownership inventory and measured transfer packet ([packet](../../scripts/audits/evidence_dose_transfer_20260930/README.md)).
- [x] Approve probiotic certainty **0–10**, applicability **0–6**, independent same-condition replication **0/2/4**. An applicable material conflict suppresses replication only. No companion Evidence or category ceiling.
- [x] Migrate probiotics through existing owners; retain CFU/trial-amount assessment in Dose, preserve clinical guards and remove the experimental/retired 12+8 path.
- [x] Prove exact approved-candidate numerical equivalence, migrate tests semantically, pass the full fast suite and obtain fresh review (Q47).
- [x] Correct D26 collagen preparation/source binding through existing owners (`c8f53b46`);285 frozen controls identical,18,018 fast checks passed and fresh review accepted. This fixes source ownership, not the remaining amount transfer.
- [x] Verify all nine uncovered benchmark groups/four retained D26 stand-ins and prepare the whole D24 denominator/publication/excess and omega decision packet (October2 combined batch,86synthetic/16real probes).
- [x] Transfer remaining generic clinical-amount judgments after approval and equivalent existing-Dose ownership. Exact positive applicable preparation benchmarks only; the four D26 safeguards were removed only after Dose coverage existed.
- [x] Integrate omega purpose/applicability mapping; carrier oil mass supplies neither EPA/DHA exposure nor clinical credit. Ordinary adult / triglyceride-purpose / prenatal map to 10.4 / 20 / 11.1 and the five excluded classes remain held.
- [x] **HISTORICAL PHASE-1 EXIT CHECK (later live-owner gap closed below):** Recheck every removed amount gate against the transfer inventory: no lost assessment and no duplicate deduction. The 344-label replay has zero status, safety, route or purpose movement.

- [x] **October5 live-owner transfer:** Zinc cold-lozenge, white-kidney-bean, D-mannose and D-aspartic-acid research exposure now belongs to the existing Dose owner. Sean approved descriptive correspondence, no new positive benchmark, retained16/22 fallback and current denominator. Matching preparation/purpose Evidence is amount-independent; generic WKB stays reference-uncertain, exact-source Phaseolean uses discrete regimens.183 raw labels measured;10 Evidence-only movers, zero Dose/status/captured Safety movement; independent review, local537 and exact-source4-groupCI37338107501 pass. Amla remains dormant/reference-only. Broader clinical coverage and fresh corpus/catalog/app validation remain open.

**Invariant:** an amount judgment cannot leave Evidence until the same judgment is already in Dose or is added to the existing Dose owner in the same change. Removing amount gates must not automatically award full Evidence marks.

### Phase 2 — Identity, roles and prominence — source fixes complete

- [x] Preserve landed Lane 2A subject ownership, Q3 single sugar/sweetener charging and Q40 cleaner-owned plant part.
- [x] Close the bounded CFU source cases `242637` / `242654` / `327966`: statement exposure and guarantee use the selected panel serving; `327966` remains 50 B through expiration. Final 455-label replay explains all nine changed payloads and preserves 446 controls. Broader alternate-serving and role classes were subsequently addressed by the Q39 and shared-owner batches below; final artifact validation remains open.
- [x] Fix Ravage cinnamon at the cleaner's functional attribution seam; retain explicit flavors, active/other membership, source paths and undisclosed member dose (Q48).
- [x] Measure Ravage and five controls, then the extended 1,259-label cohort; obtain fresh review and **zero expected failures** in the full fast checkpoint.
- [x] Correct trace-protein purpose for EAA product `66953` through shared roles and sports Evidence/Formulation/Dose consumers (Q39(b), source `3ee91eae`, pushed). Final fast suite passed; fresh review accepted clean replays. Total 49.1→37.0 is explained, Safety unchanged; five targeted and all 1,259 extended controls retain identical full payloads. EAA research remains open in Phase3.
- [x] Route `_primary_mass_floor` and related generic recovery/collagen prominence decisions through existing shared role facts. Current production reads `evidence_prominent_row_keys` → the shared role owner; identity, source-lineage, structural and deduplication guards remain. Four retained amount comparisons are the separate Phase-1/D26 transfer dependency, not an unfinished prominence-owner replacement.
  - **Integrated on main (October 1); historical pinned audit:** Codex pinned Claude production `b43a048f`, independently reproduced member-named blend headings borrowing member amounts, and committed corrections through `9f7837e8` on `codex/quality-completion`. Source facts use the existing scoring-input contract; branded-floor eligibility rejects a multi-member total containing the named branded member. The broader prototype was rejected after raw replay exposed whole-preparation regressions. The narrowed implementation preserves Mirtogenol, phytosome, Relora and standalone UC-II preparation controls.
  - [x] Independently reproduce the heading/member defect, implement failing-first owner fixes and obtain fresh review of the narrowed correction.
  - [x] Measure the narrowed fix against pinned `b43a048f`: 185/186 real labels identical; product `321351` loses a UC-II floor borrowed from its 10 g mixed-collagen total (70.4→54.8, Evidence 20→4.4, clinical points unchanged). Fifteen adversarial/control cases: eleven identical, four edited member-heading variants lose only the invalid Evidence floor. See the [audit receipt](../../scripts/audits/prominence_ownership_20261001/README.md#codex-independent-audit--october-1).
  - [x] Final full fast checkpoint at `b0c51483` (production unchanged from `c6ea928d`): **17,823 passed, 307 skipped, zero failures and zero expected failures**; exit zero. Skips include missing stored artifacts and Node-dependent console tests; these are not release validation. Focused protections: 53 passed. First complete run: 17,961 passed, 167 skipped, one stale probiotic archetype expectation failed. Its generic species credit was independently traced and the expectation corrected; all 41 archetype checks pass. Canonical-provenance canary independently passed after replacing its obsolete corpus fixture with a fresh production-boundary extraction.
  - [x] Complete the unit-selection correction packet: `c6ea928d` uses the existing converter so 10 g beats 300 mg, while exact source rows stay authoritative. Failing regression reproduced, 143 focused checks passed and fresh review accepted; all twelve frozen raw labels remain identical and all 186 controls retain identical captured payloads. No new Dose policy or benchmark.
  - [x] Reproduce and correct the symlinked manifest-path assertions (`b0c51483`); all three real-product clinical identity checks pass unchanged. The citation-parser timeout passes on focused rerun without data or timeout changes. The isolated combined checkpoint passed as recorded above.
  - [x] Reconcile and independently validate Claude's later production `68cae99a` and Q51's record-unit amount reader, retaining the Codex member-total safeguards. Combined source `a3a2d904`: 17,994 fast tests passed, 167 skipped, zero failures/xfails; seven independent consumer probes passed. Latest-Claude control replay: all 1,259 captured payloads identical; narrow 186-label replay retains the single explained UC-II correction. Earlier pinned results alone do not validate this combined source.
  - [x] Claude latest-source implementation/cohort measurement validated on `68cae99a` (17,954 passed, 168 skipped); Codex independently reconciled and tested the combined source. This is sampling, not full-corpus release validation.
  - [x] Integrate the validated combined source on main, including Q49 safeguards and Q51 record-unit comparisons. D26 was later closed; this checkpoint alone does not close the Phase 2 umbrella or authorize catalog release.
- [x] Resolve remaining alternate-serving identity/duplicate cases from raw JSON (Q39), including audience-only serving notes, inconsistent column contents and shared-form-UNII wording drift. Raw census: 108→0 repeated top-level names; 141→18 all-tree names, with all 18 retained as distinct authored branches. Never merge materially different preparations or discard label variants.
- [x] Align demonstrated dual-use active/excipient decisions through the existing shared owner without amount-based demotion. October4 census:5,770active additive-flagged rows;726flag changes across579products; final591-label raw replay plus inactive/unknown/descriptor/nutrition/legacy-source controls. Source membership and efficacy ownership stay separate. Integration receipts are recorded below and in LEDGER; final candidate validation remains open.
- [x] **Current-source Evidence-subject census:** immutable raw15,421labels/102,281subjects on380e1713;15,101resolver-complete/320partialproducts and340pending subjects across58canonicals. Every subject/source/disposition retained; existing malformedCleanholds250356/312659 remain outside successful Enrich inputs. Census completion is an audit result, not closure of newly discovered source fixes or release coverage. Receipts below and inLEDGER.
- [x] **Census-discovered source remainder:** corroborated NEM/Univestin/Triphala/fatty-oil/active VitaminC corrections are integrated; the final existing-owner batch preserves declared pepper/isolated-marker preparations, olive-oil grade, parent-local active nutrient forms and canonical source names. Generic grapefruit cannot inherit grape-seed/naringenin credit. Both nutrient adequacy and interaction thresholds use the same converter activity result; tocotrienols cannot become alpha-tocopherol. Oil/mineral source and purpose contexts remain distinct, without blanket demotion or invented duplicate exposure. Final0123889b:310-label measurements, full warnings, independent review,537local checks and all four CI groups pass. This closes corroborated source defects, not preparation-specific clinical benefit or current artifact/app/release validation.

Do not introduce the rejected mass-based demotion of purpose ingredients. Keep source-section membership separate from efficacy ownership.

### Phase 3 — Evidence research

- [x] Complete the registry-state inventory and repair the obsolete determination token without weakening specific identity/applicability holds (Q43; [receipt](../../scripts/audits/evidence_completion_20260930/README.md)).
- [x] Preserve verified probiotic preparation/population/purpose, primary outcomes, review approval and trial-family independence in production migration.
- [x] Independently identify source/strain attribution defects in the generic longum and acidophilus records (Q53); record a release hold rather than treating unchanged scores as clinical validation.
- [x] Correct Q53 through the existing registry/applicability owners: two per-entry source reviews, canonical reference-only veto, 536 frozen raw labels plus one preserved submission, and fresh independent review. All 54 DSLD score decreases are Evidence-only; existing native-strain assessments are unchanged.
- [x] Integrate Q53 final source checkpoint on main through `6a15be14`, including the corrected BB536 preservation canary; combined fast18,008passed/168skipped/zero failures or xfails.
- [x] Validate broader Evidence coverage on the fresh candidate: all102,161manifest-owned subjects, matching519reviewed RAWproducts/5,869subjects, unchanged436shared source/reference files and strict reachability corroborate the completed named determinations.264105/LA-5 remains reviewed no-qualifying evidence, with no points. The eight Q53identity/applicability exceptions12091,1834,19171,19172,19890,35694,46802,65049 retain insufficient exact correspondence and cannot gain generic species credit. Identity uncertainty remains an honest applicability hold; no unsupported positive grade is restored.
- [x] Audit the **current corrected subject set** through the shared provider on all15,421 frozen raw labels. ALA now has a completed mixed/null primary-source determination and leaves the pending list; Inulin/FOS and Sunfiber exact-source joins also leave it. Retain all340pending subjects/58canonicals with their exact row/disposition and reviewed exception classifications. Fresh release eligibility/clinical completion remains separately unchecked; resolver completeness is not comprehensive clinical revalidation of every authority record.
- [x] Finish the named omega preparation/purpose and generic/branded-formula coverage: individually reviewed preparation/population/purpose limits and44factual records retain unestablished correspondence or bounded no-qualifying evidence; current RAW/native controls and fresh all-corpus reachability agree. Tesnor/Sytrinol wiring remains verified; no new positive grade or benchmark is awarded.
- [x] Verify the nine-label Q53 and eight-family indexed/bounded source batch together; document live identity/material/outcome checks and bounded negative searches in the existing research register (October2).
- [x] Complete the remaining named clinical determinations and generic/branded source verification:44records/49references/48papers content-verified, independently reviewed source/measurements integrated, and fresh subject coverage matches. Insufficient identity and252baseline citation-debt items remain explicit; this is not universal ratification of legacy authority records.
- [x] Ensure no release-eligible subject has a pending literature determination: zero across102,161subjects. The only two unresolved material identities (307560) are explicitly points-ineligible, matching the reviewed RAWholds; insufficient identity remains a justified hold.

A completed determination may be applicable positive evidence, reviewed null/no effect, inapplicable or combination-only evidence, or a bounded no-qualifying-human-evidence review. It does not mean every ingredient gets positive points.

### Phase 4 — Dose policy packets — approved and implemented

- [x] Preserve accepted rules: known amount/applicable benchmark receives proportionate treatment; undisclosed amount has its correct zero reason; missing benchmark is not zero dose; BCAA/EAA sets are assessed once.
- [x] Produce missing-benchmark cases for one through four purpose ingredients: wiring miss, unsupported benchmark, preparation mismatch, missing amount and incidental unbenchmarked ingredient (October2 whole-batch packet;20typed cases plus unbenchmarked controls).
- [x] Show per-ingredient assessment, denominator, pillars, total, tier and publication behavior, including current `not_scored` consequences (October2 packet:all1–4typed missing-amount cases suppress public totals/pillars; export quarantine distinguished from blocked warning publication).
- [x] Produce the excess packet separating appropriateness from Safety risk, with exposure basis, form, population, duration and UL basis (October2 existing60/90mgZinc probes and current owner/config consequences; no new approved deductions).
- [x] Obtain Sean's approval for magnitudes, denominator treatment, explanations and publication behavior before implementation.
- [x] Implement only the approved decisions in existing owners and measure their effects. One-to-four-purpose demonstrations, the eight-class omega table and all frozen movers are in the final calibration receipt.

### Phase 5 — Numerical calibration and overlap

- [x] Produce the initial six-pillar numerical-ownership inventory ([inventory](../../scripts/audits/numerical_ownership_20260930/README.md)). Inventory is not calibration approval.
- [x] Finalize `fact → judgment → pillar → production symbol/config key → other observing pillars` for every live numerical rule.
- [x] Inspect all 35 Q3 legacy `POOR → SAFE` crossings individually. All 35 are Poor→Needs improvement quality aliases; Safety/Hygiene and B1 are unchanged.
- [x] Resolve duplicate deductions and ratify distinct cross-pillar judgments. Fiber fixed duplicates are removed; certification/disclosure, clean-label/B1, additive/hygiene and Dose/Safety owners are explicitly separated.
- [x] Ratify the approved magnitudes and obtain independent review of the final implementation and replay. The frozen baseline and candidate use the same 344-label raw manifest.
- [x] Explain every score/tier/verdict movement. The receipt lists all 71 movers; no typed safety/status/route/purpose movement occurred.

### Phase 6 — Flutter parity and nutrition

- [x] Implement and review the separate Flutter lane's taxonomy, numeric/zero daily-value rendering and seven diagnosed golden updates (`2de825fe`, `e21df0fd`, `d5de1023`, `ec7b1530`). Its recorded app gates passed; this is lane validation, not frozen-candidate acceptance.
- [x] Fix the pipeline's daily-value loss at the cleaner owner and verify real-product `214452` rendering with a local candidate.
- [x] Integrate and push Flutter Phase 6, app P0, verified-feed cache ownership and reviewed blocked-page clarity on app main `d6882d79`. Final combined `make check`: **3,754 passed**, analysis no issues; 72 blocked-page focused checks passed. Taxonomy byte/hash parity verified; seven golden failures closed. Simulator screenshot inspected (existing running build; final bundle acceptance remains below).
- [ ] Validate the integrated Flutter source against the final rebuilt release candidate; recheck real-product contracts/rendering and bundle parity.
- [ ] Verify nutrition/active/other sections, full label-row rendering and summary fallback: amounts, exact units, available daily values, explicit zeros and absent values.
- [x] Confirm no app calculation recreates a pipeline score, verdict, role or Evidence determination. Final15244-row production Drift/six-pillar parse compares source scores, statuses and Evidence display states;27connected screens match core hero scores/tiers/blocked status and hash-matched detail records. Current connected-screen/projection/pillar source trace confirms existing pipeline fields are rendered; presentation labels do not change clinical determinations. Receipts: app_fresh_catalog.log, final_connected_screen_retry.log, final_app_candidate_validation.json. Actual simulator acceptance remains separate.

### Phase 7 — Candidate, approval, release and live verification

- [x] Audit Sean's October 1–2 intermediate Clean/Enrich/Score run: 38 datasets, 15,421 scored artifacts, 114 matching input/code/content manifests; 46 accepted CFU/control products retain all public pillars, totals, tiers and typed safety. This is a completed checkpoint, not the final candidate: downstream snapshot guard exposed two source defects, corrected in the October 2 batch below.

- [x] Verify a fresh development corpus from **Clean**: latest `batch_run_summary_20261004_173701.txt`, source c1deb2f2,38 stage chains/114 current manifests and strict catalog build. The subsequent note-scope correction changes reference fingerprints; this completed run is historical for that display copy, not the final post-batch candidate. Final regeneration is included in the next open candidate checkpoint below.
- [x] Rebuild catalog, interaction output and canaries; run release gates and the full backstop sequentially. October7candidate2026.10.07.141113 passes catalog gates and all38manifest-owned stage chains; interaction132/132verified and byte-identical8efbpaired. Release128passed/one subsequently-covered orphan skip, every data/live gate passes; composed fullprofile22,459passed/45declared skips after three source-grounded artifact test repairs (3focused+17owner/consumer checks). Original failure receipts remain; source checks reused under unchanged fingerprints. Device/D25/publication remain separate.
- [x] Freeze candidate SHAs, config/data fingerprints, catalog generation and artifact hashes. October5 candidate2026.10.06.013007 is frozen at pipeline9f726a8f/runtimefb91849b and test-only acceptance sourcea5560b14; all114stage fingerprints match. Core/detail-index/manifests/interactions and218runtime/reference files have recorded hashes. Main integration, full/device validation and exact-candidate approval remain separate.
- [x] Produce counts/holds/statuses, route changes, newly scored/held items, largest 50 score deltas, all safer-verdict and BLOCKED changes. Frozen candidate15149products/272quarantines,37added/198removed,77shared route changes versus committed/live September22 baseline and73blocked products. Top50score deltas and pillar attribution, all safety transitions, source-level twoNMN readiness recoveries and unchanged37warned identity holds are retained. Numerical attribution is not blanket clinical approval.
- [ ] List every expected failure and release relevance; require **zero unexplained deltas** and no release-critical expected failure.
- [ ] Resolve release-gate decisions in D25 and approve the exact candidate/manifest. New code-push authorization is not catalog-release authorization.
- [ ] Publish through the existing release chain only after exact-candidate approval.
- [ ] Verify live core/blob parity, interaction checksums, bundle/OTA generation and representative app rendering.

Any candidate change after approval requires a new freeze and approval.

What follows Phase 7 (and the few items that can run beside it) is in the [product roadmap](PHARMAGUIDE_PRODUCT_ROADMAP.md); this plan is its Phase 0.

## Added and discovered since the original plan

| Item | Finding/change | Outcome and evidence |
|---|---|---|
| Probiotic redesign | Retired dose-coupled 12+8 architecture could distort category scoring | Approved shared certainty/applicability/replication model; Q47 |
| Certainty parity | Equivalent research could score differently by source path; exact formula could borrow member/species research | Shared certainty, isolated formula attribution and winning-family applicability; accepted frozen replay |
| Population fallback | Pediatric contexts could lend purpose applicability to an adult label | Shared population guard and failing-before/passing-after regression; product `337873` restored to accepted result |
| Migration provenance | Changed config retained its previous version | New `1.22.0-probiotic-family-evidence`; prior fingerprint history preserved |
| Migration tests | Old fixtures encoded retired policy/copy/diagnostics | Assertions migrated by protected invariant, not blindly refreshed; independent review |
| Ravage | Generated flavor identity alias assigned flavor function to active Cinnamon Extract | Existing declared alias lookup now owns functional flags; Q48, zero xfails |
| Golden Milk | The same correction restores cinnamon to Evidence-owner metadata | Scores unchanged; explicitly measured and reviewed |
| EAA trace protein | Raw `66953` was borrowing whey purpose in Evidence, Formulation and Dose | Shared role and consumer correction measured; five targeted controls and all 1,259 comparison labels unchanged; final 17,915-test checkpoint passed and source pushed; EAA research remains open |
| Review-discovered consumer paths | Formulation could conflate calibration subtype with purpose; Dose still selected protein independently by its flat credit | Both corrected before acceptance; genuine protein/stimulant and actual EAA Dose-driver regressions added |
| Stale handoff wording | Historical transfer docs still described the retired probiotic decision as pending and source as unpushed | Historical inventory labeled; approved Q47 and source-push status synchronized; catalog release remains separate |
| Remaining prominence | Generic recovery/collagen and sports consumers also select primary independently | Added to Phase 2 scope so fixing one helper does not leave another decision behind |
| Prominence owner gaps (in progress) | Role owner counted a lineage-owned supplying complex in its mass ratio (Solgar `218600`); generic recovery lent species records to live probiotic organisms (`232059`); recovery re-stamped a record enrichment already linked, narrowing its refs (`217818`, `1838`); the floor had used blend-heading totals as member doses (creatine modules, fiber blends, Sensoril); the product-level brand predicate missed hyphenated identifiers (UC-II, BCM-95, EGb 761) | Corrected on the Claude branch with failing-first regressions; branded headings that name their record keep their floor; final measurement pending (Q49) |
| Role-owner unit gap (open) | `classify_ingredient_roles` cannot size `mg NE`, `mcg DFE`, `mcg RAE` or vitamin D IU, so those rows never become purpose rows | Measured fix flipped 4 products to `not_scored` because Dose readiness cannot assess DFE/RAE rows once material; reverted, open cross-owner item (Q49) |
| Concurrent main | Release gate/storage changes arrived during integration | Reconciled and replayed before acceptance; D25 remains an explicit decision queue |

## How to move a checkbox

1. Reproduce the defect from raw/source facts and name the existing owner.
2. Add a failing production-boundary regression, then fix that owner.
3. Run covering tests; measure clean frozen inputs with unaffected controls.
4. Classify every movement, pass the required checkpoint and obtain fresh review.
5. Record implementation/measurement/review/source-push/catalog-release states in the existing ledger; link the receipt here and check only the completed item.

Codex alone edits shared pipeline owners. Research and Flutter can proceed in separate worktrees with explicit file ownership. A fresh reviewer validates independently. Preserve rejected drafts and historical measurements; never assume an audit's “fixed” means it shipped.

## Original agreed plan — frozen September 30 scope

This is the original phase outline and acceptance boundary retained for comparison. The execution checkboxes above update progress and discoveries without replacing its architectural requirements.

| Original phase | Original deliverable and exit requirement |
|---|---|
| 0 | Reconcile SHAs, dirty files, unique commits, worktrees and inputs. Establish generated versus curated ownership before regenerating missing files. Exit: reproducible baseline and accurate ledger. |
| 1 | Inventory generic/resolver/probiotic/omega amount judgments; same-change transfer to existing Dose owners, with all-route mappings and frozen replays. Benefit uses minimum directed use; excess/risk uses maximum. Blend totals never become member doses. Exit: no lost assessment, duplicate charge or unexplained movement; approve policy magnitudes before integration. |
| 2 | Shared `classify_ingredient_roles` owns prominence; `_primary_mass_floor` stops selecting primary by mass. Preserve Lane 2A, fix Ravage/trace protein/serving duplicates, preserve active/other membership, Q40 and one brand resolver. Exit: justified roles from raw JSON to Flutter and no hidden release-critical expected failure. |
| 3 | Complete Evidence determinations, not necessarily positive evidence. Verify primary sources and keep foods/extracts/preparations/branded interventions distinct. Named probiotic, omega and branded-formula lanes. Exit: no pending release-eligible subject; insufficient identity remains held. |
| 4 | Missing-benchmark and excess-dose decision packets, including preparation mismatch and one-to-four purpose ingredients. Separate appropriateness from Safety. Exit: Sean-approved magnitudes, denominators, copy and publication behavior. |
| 5 | All six pillars and every numerical rule in a required ownership table; inspect all 35 Q3 crossings, overlap and subsequent safer verdict changes; ratify reviewer brief and freeze benchmark. Exit: approved magnitudes, independent review and explained movements. |
| 6 | Flutter taxonomy, seven screenshot diagnoses, label nutrition/summary, exact units/DVs/zeros and consumer-only scoring contract. Exit: candidate contract parity and real-product rendering. |
| 7 | Fresh Clean corpus without publication, catalog/interaction/canaries, sequential gates/backstop, frozen release manifest with xfails and zero unexplained deltas. Sean approves exact candidate; publish through existing chain and verify live. Changed candidate requires renewed approval. |

Original reported baseline: main/origin `880b17a7`, clean; 17,950 fast tests passed, 40 skipped and one expected failure. Lane 2A, Evidence classification closure, Q3 and Q40 were integrated; rejected Dose draft unlanded. Ravage, Evidence/Dose coupling, final calibration, Flutter parity/screenshots, final corpus and publication were outstanding. This is a **historical starting statement**, not today's verification result.

Original fixed boundaries remain: six maxima 20/20/20/15/15/10, existing public fields/statuses/mirrors, existing owners only; no second scoring system. Original acceptance remains: no lost assessment, unexplained deltas or release-critical expected failure; justified identity holds and completed Evidence determinations; current provenance, passing pipeline/app gates and successful post-publication verification. A deferred expected failure requires explicit approval and proof it cannot affect shipped products.

## October 1 integration and cleanup receipt

- [x] Push validated pipeline source and Q49/Q51 integration register to main (`de63a5f0`, tested production `a3a2d904`); final fast: 17,994 passed,167 skipped,zero failures/xfails.
- [x] Push combined Flutter source to main `d6882d79`; final analyzer and 3,754 tests passed.
- [x] Remove clean merged lane worktrees and branches after verifying their tips are contained in published main. Remove the requested `dose-map-base` scratch checkout. Preserve rejected/superseded experiments and ignored handoffs in recoverable archives.
- [x] Implement, measure and independently review Q53 generic probiotic source/applicability corrections (`0acde33e`; benchmark-only follow-up `de3d0353`). Exact-strain registry and all numerical policy magnitudes are unchanged.
- [x] Complete and integrate Q53/Q52 final source checkpoint through `6a15be14`:18,008 passed,168 skipped,zero failures/xfails; fresh review accepted. Q52 corrects both CoQ10 copy branches through the existing rule owner; severity/gates/other siblings remain unchanged.
- [x] Complete D26/D24/omega implementation and approved calibration before the fresh corpus/release sequence.
- [ ] Complete remaining release-eligible identity/clinical determinations and the broader dual-use source audit. Q53 holds and new interaction copy require fresh generation before release.
- [x] Push app reference metadata parity to main `be368cfe`: clinical payloads unchanged, all 32 canonical artifacts synchronized, analyzer clean and 27 focused tests passed. Remove its clean merged worktree/branch; private handoff preserved.

Durable replay, logs, simulator capture and cleanup archives: `/Users/seancheick/pg_quality/integration_20261001/`. App Dependabot branches are new unreviewed dependency proposals and remain untouched. Website main already contains its reconciled work; untracked `axis-proposals-for-review.csv` is preserved. No catalog, interaction DB, Supabase or OTA publication occurred.

Final October1 source batch: Q53 and Q52 are implemented, measured, independently reviewed and integrated on main; source checkpoint `b575104c` is pushed and verified equal origin with a clean checkout. Full frozen corpus, final exported-verdict review, generated interaction artifact, release/full gates, exact candidate approval and runtime publication remain open. The current source gate does not replace those stages.

- [x] Verify pipeline/app source mains equal origin and clean; archive/remove the finished clinical/reference worktrees and delete their contained branches. Actual worktree inventories now contain primary mains only. Preserve private handoffs, measured inputs/reports and rejected experiments; retain unreviewed dependency proposals and the user-owned website CSV.


## October 1 D26 continuation — current working checkpoint

- [x] Reconfirm Q53/Q52 source corrections are already integrated on main `0a24804f`;
  preserve reference-only species records and exact-strain boundaries.
- [x] Fix D26's recovered collagen study binding at the existing Evidence recovery/
  source-reference owners (`040db5c4`, `0c4fb894`, `fe3d39a0`). Peptide exposure cannot
  borrow another preparation's amount; ambiguous or blank provenance fails closed.
- [x] Preserve both declarations of one exactly named peptide preparation (raw269490),
  with maximum applicable amount rather than summed duplicate quantities.
- [x] Measure285 frozen raw labels with zero capture deltas; owner sweep794passed/
  14artifact skips. All existing magnitudes and four retained D26 safeguards unchanged.
- [x] Fullfast18,018passed/168skipped/zero failures or xfails,749.09s; fresh reviewer accepted source and verified byte-identical285-label captures. Source integrated/pushed at `c8f53b46`; main/origin verified equal and clean.
- [x] Complete broader D26: verified Dose coverage + D24 decision packet + approved
  omega purpose/magnitude mapping → equivalent Dose assessments → remove Evidence
  amount gates/stand-ins. Closed by the approved October 2 implementation and calibration receipt.
- [ ] Complete Q53's nine-label clinical coverage queue; priority12091 SD-5845 trace.
- [x] Calibrate after ownership/policy stabilization; finish numerical ownership
  table, individual35 Q3 crossing reviews and all unexplained-delta classifications.
- [x] Run and inspect the fresh final Clean corpus with publication disabled.
- [ ] Rebuild candidate artifacts, run sequential gates, freeze the manifest,
  obtain exact candidate approval, publish and verify live behavior.

Owner: `generic_evidence::_recover_contract_evidence_matches` / `_stamp_recovery_source_ref`
/ `_converted_product_dose` — evidence: failing artifact regressions, frozen raw269490
and285-label replay. Will NOT create: scorer, registry, preparation parser, Dose engine,
public field/status or app calculation. Detailed current packet:
[Evidence→Dose continuation](../../scripts/audits/evidence_dose_transfer_20260930/README.md#d26-preparationsource-binding--october-1-continuation).
Current durable receipts: `/Users/seancheick/pg_quality/d26_peptide_20261001/`.

The accepted master plan retains Sean's preference to consider distinct Dose
appropriateness and Safety risk consequences for excess. Older D24 prose favoring
Safety alone is historical; neither formulation authorizes a duplicate charge or
unapproved magnitude. Benchmarks/denominators and omega magnitudes remain explicit
Sean decisions under Phase4, rather than implicit choices by an implementer.


## October 1 CFU guarantee continuation — source complete; release validation pending

- [x] Reproduce raw12091: 5 billion at manufacture plus an unquantified effective
  level at expiry incorrectly became a 5-billion expiry guarantee.
- [x] Fix the existing enrichment count/warranty owner; preserve numerical Dose
  multipliers and the approved Evidence model. Boundaries include differing counts,
  multiple statements, replaced totals, every counted aggregate contributor,
  parenthetical claims and explicit subgroup versus total declarations.
- [x] Preserve matching guarantees after final total selection, fully expanded
  CFU notation, explicitly probiotic Cell(s) rows, and fixed daily-serving
  equivalence through the existing serving-frequency owner.
- [x] Consolidated CFU/structural/nutrition boundary: 1,632 passed,16 skipped; final allocation controls:172 passed,5 skipped. Earlier105-check receipt remains historical.
- [x] Reconfirm all five published Transparency pillar scores restored:256934 (8.6),274061 (9.1),274094 (9.7),277033 (9.7),297668 (9.0). Receipt:`five_transparency_restoration_receipt.json` in the durable CFU folder. Mood+ retains9.1; its internal raw component is9.1127 versus baseline9.1021, so this is not a claim of byte-identical internal pillar objects.
- [x] Complete clean1,259-label CFU replay and classify all33 score movements;717 omega controls identical, no Evidence/Safety/Verification/route/status/purpose changes. Independent review accepted source.
- [x] Complete final portable full-fast checkpoint at `91987d74`:18,079 passed,168 skipped,zero failures/xfails.
- [x] Complete pipeline main integration/push (`0f9ca406`) and contained-lane archive/branch cleanup; ignored handoff and frozen receipts preserved outside the worktree.
- [x] Close the named label/basis discrepancies `242637`, `242654` and `327966` through the shared serving/count/warranty owners. Broader dual-use source classification remains separately open in Phase 2.

Owner: `SupplementEnricherV3::_extract_cfu` / `_extract_guarantee_type` /
`_collect_probiotic_data`; `serving_frequency::resolve_daily_serving_range` for
frequency. Evidence: raw12091, failing source regressions,105 focused checks and
production Dose consumers. Will NOT create: CFU parser/registry, scoring engine,
public field/status, or numerical policy. Historical isolated source `83fc2ae5`; initial
candidate `99aa837b` was rejected after replay/review and is not accepted by itself.
Durable receipts: `/Users/seancheick/pg_quality/cfu_guarantee_20261001/`.

The bounded SD-5845 source search remains a research receipt, not a completed
negative Evidence determination. The nine-label Q53 clinical queue stays open.
At this historical checkpoint D26, D24/omega approvals, calibration and final corpus/release were unchecked. The October 3 audit closes the first three; the final corpus/release remains open.


## October 1 execution correction — independent quality and safety

Sean explicitly approved removing the mixed quality/safety ladder. This supersedes
older instructions that make POOR the public verdict of the lowest quality tier.
Quality ratings are Poor → Needs improvement → Good → Very good → Excellent →
Exceptional. Safety is `product_safety_status`: not assessed, no known catalog
concern, caution, unsafe or blocked, with banned/recalled reasons preserved.
An improvement in quality is never described as an improvement in safety.

Owner: `quality_score::assemble_quality_score` for quality, `scored_artifact::_product_safety_status`
for safety, `release_safety/catalog_diff::_products` for release comparison, and
Flutter `catalog_product_semantics::catalogProductSafetyStatus` / `ScoreTier` for
rendering. Evidence: production consumers, ownership matrix, failing boundary
regressions and independent cross-repository review. Will NOT create: another
score, status field, safety classifier, quality ladder or app-side calculation.

- [x] Remove quality-tier conversion into POOR/SAFE. Retain hard safety and
  publication/readiness gates; current scoring never emits POOR.
- [x] Correct shared vocabulary. Keep POOR only to read older cached catalogs,
  with no safety claim; preserve independent quality and safety readers.
- [x] Make release comparison consume existing `product_safety_status`; keep
  exact safety, tier and score approval states and fail closed on missing or
  unknown typed safety. Safety tables no longer show POOR → SAFE.
- [x] Remove obsolete Flutter scanner verdict-color and duplicate quality-color
  helpers. Quality 39/60/97 cannot alter any typed safety status. App analysis
  clean; 92 focused checks passed at `a5b705ad` (not integrated yet).
- [x] Independently review bounded source; all non-metadata numerical config
  values are identical. Version 1.22.1 preserves the earlier fingerprint.
- [x] Complete final1,259-label separation replay: only four config-provenance paths change. All46 production-artifact probes retain scores, tiers and typed safety; zero newly emitted POOR.
- [x] Complete portable pipeline fast at `91987d74`:18,079 passed,168 skipped,zero failures/xfails.
- [x] Complete app `make check` at merged source `63eeabff`: analysis no issues;3,742 passed,zero failures,1:56. Concurrent main `f8c08d80` preserved and reviewed;12 focused stack-action checks passed. No golden images updated.
- [x] Integrate/push both repositories and remove contained Git worktrees/branches.
  Pipeline `0f9ca406`, app `63eeabff`; final documentation receipt follows.
  No runtime catalog publication is authorized here.

Process correction: consolidate each defect class across source preservation,
selection and consumers; run focused tests first, then freeze the completed batch
for measurement and one final broad checkpoint. A real regression found in that
measurement must be corrected before integration. Do not expand a source cleanup
into unapproved numerical policy or clinical coverage claims.

Final export followup `50a2fb7d`: existing `build_decision_highlights` no longer selects caution copy from legacy SAFE/POOR/CAUTION. It reads typed safety and quality-assessment readiness independently; additive/danger copy is retained. Two reproduced failures plus missing/unknown-safety and retained-danger controls cover this class. Export-owner sweep:2,766 passed,72 generated-artifact skips. Independent review accepted the narrow fix. The interrupted broad rerun (8,894 passed,131 skipped) is not a final acceptance receipt; the final broad gate follows this last production change.


## October 1 final source integration receipt

- [x] Q54 CFU producer/parser/aggregate/warranty consolidation implemented, measured, independently reviewed and integrated.33 frozen score movements explained;717 omega controls unchanged.
- [x] Q55 quality/safety separation implemented across scoring, public artifact, export copy, release comparison, Flutter consumers and current agent doctrine. Scores/maxima unchanged by separation; no newly emitted POOR.
- [x] Final pipeline fast:18,079 passed,168 generated/live-opt-in skips,zero failures or expected failures (751.29s), source91987d74.
- [x] Final merged app make check:analysis zero issues,3,742 passed,zero failures (1:56), source63eeabff. One derived vocabulary-manifest checksum fixed through its canonical builder; no golden images changed.
- [x] Independent review accepts both source candidates. Both main branches pushed; each repository has only its main checkout and local main branch. Fresh Dependabot branches remain because they contain real work.
- [x] Managed pipeline lane archived and contained branch removed; app lane removed after integration. Ignored handoffs and all historical/final evidence preserved in `/Users/seancheick/pg_quality/cfu_guarantee_20261001/`.
- [ ] Final runtime candidate and release acceptance: incomplete; no catalog/Supabase/OTA publication in this batch.

The stale quality-completion UI attachment is owned by another chat and cannot be archived from this chat. It has no current Git worktree or branch; it is not pending implementation. The archive tool refused cross-chat ownership, and no source was deleted to work around that limitation.

Historical next items were D26, D24/omega, Q53 clinical determinations, three raw serving/title discrepancies, calibration and a fresh final corpus. Later receipts close D26/D24/omega, the three named discrepancies and numerical calibration. Q53 clinical holds and the fresh corpus/release manifest remain open.

Sean will run the full pipeline when ready; Codex will inspect its completed artifacts afterward. Do not start the hour-scale corpus job merely to keep this chat active. Source checks and the full runtime corpus remain distinct.


## October 2 — Audit of Sean's pipeline and owner corrections

The run `batch_run_summary_20261001_231906.txt` completed Clean/Enrich/Score
from 23:19 EDT October 1 to 00:20 EDT October 2 on baseline `fa8c50bc`.
All 114 manifests and owned-file hashes match across 38 datasets / 15,421
unique scored products. The strict snapshot guard stopped with **7 failed,
28 passed**; three numerical changes and four compatibility-only changes were
independently investigated. Distribution artifacts remain September 29; this
run did not rebuild or publish the current catalog.

- [x] Confirm the prior 46-product CFU/Transparency/control acceptance receipt
  against actual run outputs, with zero public pillar/total/tier/typed-safety
  differences. All five Transparency repairs survive the actual pipeline.
- [x] Explain Silymarin `183275`: its label's cleaner-owned seed disclosure
  justifies Formulation 18.7→20 and quality 89.3→90.6 under existing Q40 rules.
- [x] Reproduce and correct CVS `18141`'s unsupported ALA→marine omega
  attribution at the existing curated applicability owner. Preserve all valid
  marine sibling rows and their identities, independently of label order.
  Restore quality 52.3 rather than accepting unsupported 62.7. This identity
  correction does not remove an amount gate or complete the omega policy lane.
- [x] Close the same marine attribution class on anonymous EPA/DHA aggregates and mixed ALA/EPA/DHA headings: remove unsupported ALA aliases, carry only the existing provider's exact-reference identity, and honor reviewed accepted identities in all Evidence routes. Stale names and singular IDs cannot revive rejected credit; valid marine siblings keep their applicable Evidence. The exact-reference provider identity also reconciles populated raw canonical namespaces, without changing label text, form or quantity. Source-only and ambiguous identities are protected. No member amount is borrowed.
- [x] Reproduce and correct Q40's lost cleaner plantPart in a botanical blend
  projection: Adrenal `204571` restores quality 46.9 rather than accepting
  44.3. Exact linked child facts survive; unrelated/conflicting facts and text
  inference earn no credit. Blend totals remain blend totals.
- [x] Extend the existing canary freezer/manifest to pin `quality_tier`,
  `product_safety_status` and `quality_assessment_status` independently.
  Legacy POOR→SAFE compatibility changes are not improvements in safety.
- [x] Complete the bounded raw replay, final fast gate, final independent
  receipt and source integration/push for this batch: source `b7eeb178`,
  pushed main `54a374cb`; 18,101 passed/168 skipped/zero failures or xfails.
  Final 1,496-label replay: 1,472 totals unchanged; 13 Formulation increases and
  11 Evidence decreases, all individually explained. Other pillars, route,
  subroute, purpose and scoring status remain unchanged. Six valid marine
  namespace controls and three mixed EPA/DHA controls retain baseline scores.
  46 public controls and 33 canaries match; 36 snapshot checks pass. Two quality
  tier crossings improve and nine decline; these are not safety changes.
  Intermediate 27/30-mover captures are superseded/rejected, not calibration
  inputs. Current receipts: `candidate_verified.jsonl`,
  `numerical_delta_receipt_verified.json`, `final_fast_verified.log` and
  `independent_review_final.json` in the durable audit folder.
- [x] Regenerate and inspect the Clean/Enrich/Score corpus after the final source correction; all38 stage chains and114 manifests are current.
- [ ] Rebuild and validate the catalog/interaction/Flutter release candidate;
  corpus regeneration alone does not close Phase 7.

Owner: `clinical_applicability::assess_clinical_applicability` and
`backed_clinical_studies/INGR_OMEGA3` for intervention scope;
`scoring_input_contract::_derive_top_level_botanical_blend_evidence` carries
the cleaner's existing plantPart; existing snapshot manifest/freezer owns
internal regression pins. Evidence: raw DSLD `204571`, live PMID31567003,
strict 13-citation entry check, production-boundary regressions and independent
review. Will NOT create: another scorer, normalizer, role classifier, clinical
registry, count parser, public field/status or numerical policy.

Remaining unchecked Phase 0–2 items retain their existing dependencies.
D26 equivalent Dose coverage, D24/omega decisions, Q39 serving variants,
dual-use roles, final subject census and the Q53 clinical queue are not
completed by this run. Raw CFU/serving/title cases 242637/242654/327966 remain
explicitly open; do not infer serving-basis agreement from a count alone.
Detailed measured receipts: `/Users/seancheick/pg_quality/post_pipeline_20261002/`.


### October 2 — probiotic companion regression and declared enzyme activity audit

- [x] Independently reproduce the original three failures on `014c61e9`
  (3 failed / 5 passed), inspect actual raw labels and frozen enriched drivers,
  and integrate Claude's test correction `3e7e3cd7` as the baseline.
- [x] Strengthen companion tests: only eligible bromelain may earn the entire
  raw Evidence total; native probiotic credit remains zero. Four adversarial
  cases reject unrelated credit, extra credit, inactive source and an
  unaccounted total. The labels omit member mass, but declare activity; a
  legacy `inactive_non_scorable` mirror is not an Other Ingredient section.
- [x] Correct explicit `FCC (PU)`/`FCC PU` spelling at the existing activity
  extractor, preserving the existing `FCCPU` assay and exact raw source path.
  No assay-to-mass conversion, member-mass borrowing or registry change.
  Unicode suffix rejection is retained; the two added malformed-unit
  regressions failed before the final boundary correction and pass afterward.
- [x] Verify 101 focused tests with the user's existing corpus; without the
  corpus, companion tests retain 5 passed / 7 skipped. Twelve format/boundary
  regressions pass. Freeze and replay 16 raw labels (15 initial + spaced-unit 322514) on baseline `3e7e3cd7`
  and candidate `59ed4cea`: zero total, pillar, route or scoring-status
  movements. Nine labels regain ten declared activity assessment rows;
  related disclosure/readiness counts and existing completeness drivers
  follow those facts. No unexplained metadata movement.
- [x] Obtain fresh-context independent acceptance: initial two files
  independently passed 92 tests / 7 corpus skips; final incremental review
  passed all 11 extraction cases. Integrator final portable checkpoint:
  94 passed / 7 corpus skips. Reviewer reproduced unchanged 15-label
  public results. This is extraction/ownership validation, not clinical
  ratification of the bromelain record or completion of Evidence research.
- [x] Complete this batch's full fast checkpoint and source integration/push:
  source `59ed4cea`, 18,133 passed / 168 skipped / zero failures or xfails,
  937.94s. The interrupted earlier run is superseded, not passing evidence.

Owner: `scripts/scoring_input_contract.py::_extract_enzyme_activity` and
`get_evidence_subject_rows` — evidence: existing shared scoring-input matrix
owner, production callers, explicit raw declarations and production-boundary
regression. Will NOT create: another parser, scorer, subject list, registry,
assay unit, dose conversion, public field/status or numerical policy.
Receipts: `/Users/seancheick/pg_quality/probiotic_companion_audit_20261002/`
(`baseline.jsonl`, `candidate_final.jsonl`, `delta_final.json`, `receipt.json`,
`independent_review.md`, `fast_final.log`).

At this historical checkpoint D26, D24/omega, Q53 clinical coverage, serving
discrepancies, numerical calibration and the final corpus/release were open.
Later receipts close D26/D24/omega, the named serving discrepancies and
calibration. Q53 holds and the final corpus/release sequence remain open.

## GOS/Bimuno and PreforPro source checkpoint — October 2

- [x] Verify each preparation against primary methods/results: Bimuno powder versus active GOS; PreforPro capsule mass versus phage potency; populations, positive/null endpoints and funding.
- [x] Correct the two existing IQM descriptions. Remove unconditional GOS efficacy/tolerability and phage infection/beneficial-flora/immune claims. Preserve the studies' bounded findings, including PHAGE-2's combination-only design and lack of significant between-group symptom changes.
- [x] Reproduce both defects before correcting them; 243 focused checks pass. Canonical patch changes exactly the `prebiotics` and `bacteriophages` parents, and only their two notes. Citation verification: nine topic matches, zero mismatches (five newly cited reports, four unchanged sibling citations); primary reading supplies the clinical interpretation.
- [x] Measure 39 frozen raw labels: all 30 source-text matches plus nine controls. Every scored capture is unchanged. GNC Bimuno/GOS labels 219246, 304444 and 318195 remain 55.3 with Evidence 0; Thorne 323127 remains 51.0 with Evidence 0.
- [x] Independent source review finds no factual blocker; identity, numerical values and approved consumer notes remain unchanged.
- [x] Combined checkpoint: source `c527c43c`, CI37069282386 all four shards green (18,224 passed /183 declared skips); local527 passed /24 approved opt-in skips,173.46s, skip guard passed. Integrated with this accompanying plan receipt; clinical and release gates remain open.
- [ ] Complete clinical grading and preparation-specific Dose applicability. GOS and phage zero Evidence scores do not mean no human research. Current fiber-mass Dose credit is not proof that the product matches a studied preparation or potency.
- [ ] Release validation/publication through the existing final corpus and approval gates.

Owner: `scripts/data/ingredient_quality_map.json::prebiotics.forms.galactooligosaccharides (GOS).notes` and `bacteriophages.forms.bacteriophage blend.notes`. Evidence: matrix/glossary, primary trial methods/results, canonical patch, production replay and independent review. Will NOT create: a scorer, registry, parser, public field, benchmark or numerical policy. Baseline `bf12f605`; source `c527c43c`. Receipts: `/Users/seancheick/pg_quality/gos_phage_review_20261002/`.

**Next at this checkpoint:** finish the probiotic strain/formula clinical queue and assemble the cross-family certainty/applicability and Dose packet. The later approved batch completes the Dose packet, removes D26 safeguards after equivalent ownership and completes numerical calibration. Unresolved clinical determinations and release remain separate open gates.

Measurement limit: baseline provenance includes five ignored FDA data/cache files absent from the candidate checkout. Independent review confirms matching raw hashes and all39 successful scored captures are byte-identical; this establishes bounded output equivalence, not identical full environments or release readiness. The existing research register now includes the cross-family decision-input table; it does not approve grades or Dose magnitudes.

Next bounded source finding: primary PMID36198994 describes LA-5 alone versus fluconazole for candidiasis. The next reviewer must independently confirm that report and the current `STRAIN_ACIDOPHILUS_LA5` wording before correcting its combination-only description. It does not establish gut-health efficacy, treatment equivalence or Solgar preparation/dose correspondence. Research receipt: `/Users/seancheick/pg_quality/q53_followup_20261002/primary_review.md`. SD-5845 remains unresolved; Member's Mark Bioflora has no disclosed strain and must not inherit another manufacturer's formula evidence. These are research findings, not implemented registry corrections.


## October 2 — Q65 integration and stale-branch cleanup

- [x] Independently compare Claude31113c16 with main dedc6b8e: retain main's policy-specific ban/recall owner; additional coverage and dead, unconsumed decision_highlights.danger removal retained.
- [x] Exact candidate CI37080103407 passed; main-checkout local gate527passed/24declared opt-in skips, skip guard passed136.52s. Main fast-forwarded and pushed to31113c16. No catalog release.
- [x] Delete local/remote codex/edta-release-exemption, codex/q64-number-boundary and claude/jolly-pike-10e4ca after containment checks. Preserve Claude state/config before removing its clean completed worktree.
- [x] Archive the superseded clinical-completion-batch worktree recoverably and delete its local/remote branch. Four commits are retained in codex/q53-calibration-completion; range-diff and production-file comparison establish preservation, not release validation.
- [x] Integrate the Q53/calibration lane after current-main validation. Its source and later release-critical corrections are contained in current `main` through `5246ad20`; exact-source CI and the local corpus gate are green. Runtime release remains open.

Cleanup receipts: /Users/seancheick/pg_quality/branch_cleanup_20261002/; accepted local log: /Users/seancheick/pg_quality/q65_cleanup_local_20261002.log. The historical calibration branch was integrated and is no longer a release dependency. S1 detail-blob versus core-column observation remains in Q65; removal of danger does not establish that every report axis is live.

### October 3 exclusion checkpoint — final source5cf34928, not release-complete

Eight of45 prior-CAUTION catalog exclusions are resolved by verified source/ownership corrections.37remain held; no safety gate changed in the47-label raw replay. Source fixes, focused verification, independent review, exact-CI/local acceptance and integration are complete. Historical exact-source corpus verification is complete; newest-candidate release and hands-on Flutter audit remain unchecked. This does not close clinical holds, the citation backlog, broader source-section review or publication. Evidence and ownership: existing [execution LEDGER](../../scripts/audits/pending_items_20260926/LEDGER.md), durable `/Users/seancheick/pg_quality/q53_release_20261003/form_remediation/`.

Combined CI then exposed preparation-projection regressions. Source3d002d99 corrects reviewed alias preservation and member-mass ownership;169owner/consumer checks plus12focused regressions pass. The expanded immutable51-label replay retains all8restorations and unchanged safety/dose-safety objects. Tesnor, Sytrinol and Sensoril controls stay unchanged. A separate source-verified false Mirtogenol→bilberry alias is removed:23186866.8→54.1, with unsupported Evidence15.6→0 and existing limited-assessability Dose fallback9.5→12.4. Exact combined CI/local, measured review and integration passed; newest release/app validation remain pending; no phase is closed by this checkpoint. See the existing LEDGER and durable preparation-control receipts.


## October 4 — independent audit of Claude dose/UL and safety benchmark batches

- [x] Verify landed batches against current main6ea851dc: ef893234 dose/UL source, caption/aggregation and exact copper correction changes; dd2769ad declared-nutrient conversion, safety reason and Mirtogenol/gold tests. No scorer, status, threshold or clinical policy added by this audit.
- [x] Recheck all six UL-basis notes against live NIH ODS sources. Read the three official NIH label PDFs5862/5864/18529: each prints Copper1mg50%. The exact reviewed corrections are justified; owner sign-off remains pending, never attributed to an agent.
- [x] Validate current Flutter reference data through the canonical sync --check: RDA/UL, medication depletions, taxonomy, timing rules,27vocabularies and32manifest artifacts pass. Depletions are a built artifact, not a byte copy of source JSON. Active local app catalog changes belong to the release lane and were untouched.
- [x] Reproduce missed nonverdict explanations: moderate/elevated caffeine and undisclosed non-preworkout review hid actionable dose signals. Five assertions failed before repair. Reviewer identified dormant generic B0_STATUS_* fallback; two additional assertions failed, and the production gate test proves it records a note without a verdict.
- [x] Fix existing gate_safety::stated_safety_signal in b2f8388a/dffbb80a. Extend its advisory classifications, retain flags and sole-advisory fallback, preserve high/undisclosed stimulant and quarantine drivers. No quality/Safety/status policy changes.
- [x] Focused owner/consumer/benchmark checks151passed plus the additional generic-status gate node1passed. Independent final review16passed, adverse controls accepted. The existing44dose and22regulatory cases pass; coverage is bounded, not proof of every safety family.
- [x] Measure projection on15459local stored records/96files:107reasonchanges (43caution dose explanations:42ordinary/onecritical;64advisory fallback reorders). This is not a frozen complete shipped-corpus census. Frozen9raw-label replay versus6ea851dc has identical captured scores/pillars/roles/routes/statuses/safety-gate/dose-safety objects; the replay capture omits safety_signal_reason, so its separate projection census and scored regressions verify that field.
- [x] Reason-only exact branch CI37210341807 passed at e6937db5.
- [x] Combined Vitamin E source candidate103b699e pipelineCI and final local checkpoint passed (receipts below); earlier pre-edit queue stopped without a pass.
- [x] Integrate the audited changes on Sean's explicit instruction: pipelinefed96040/app3553342c pushed to main after exactCI. Prior6ea851dc catalog receipts remain historical; new source requires a fresh candidate freeze, never silent publication.

Owner: scripts/unit_converter.py::UnitConverter.convert_nutrient / _find_conversion_rule; existing enricher RDA/UL producer; scripts/scoring_v4/gate_safety.py::stated_safety_signal; canonical reference sync; existing curated corrections and gold fixtures. Evidence: source diffs/callers, live primary texts/PDFs, fail-first production tests, frozen replay and independent review. Will NOT create: another scorer/converter/reason selector, public field/status, registry or scoring policy. Receipts: /Users/seancheick/pg_quality/claude_dose_safety_audit_20261004/; audit preserved active release/app files; subsequent main integration is recorded above.

Next: finish exact release/full/app gates and individually explain frozen catalog safety/large-score/tier changes; reconcile the reason and Vitamin E audit corrections before final freeze. Remaining gold coverage: proprietary blends/missing data, scoring controls, strain-level identity and explicit recall cases. Neither a226case count nor green tests establishes those families complete.

### Vitamin E audit extension — October 4

- [x] Reproduce a clinical basis defect left open by the reference-note correction: synthetic 2000 IU supplies 900 mg nutritional activity but approximately1800 mg physical alpha-tocopherol for the UL. Main incorrectly compared900mg with the1000mg UL. NIH ODS states that the UL includes all eight synthetic stereoisomers; nutritional activity and UL exposure are separate quantities.
- [x] Correct existing UnitConverter/enricher owners (971af205,27d9b751). Keep benefit at minimum directed use and UL exposure at maximum use. Use existing safety_exposure; no new public field, scorer, parser, registry, threshold or magnitude. Unknown/mixed forms retain conservative physical bounds, never confirmed over-UL findings; standalone compound masses cannot become parent nutrient activity. Equivalent mg/mgAT/g/mcg and IU/U/UI retain their lineage. Six mass-alias regressions failed before the final fix.
- [x] Final affected pipeline slice169passed4.99s, including22parent/compound mass-unit cases; existing44dose gold cases remain passing with corrected Vitamin E expectations. This is focused validation, not a full corpus or release receipt.
- [x] Measure committed source27d9b751 against main6ea851dc on19frozen raw labels (all7stored high-exposure cases,10lower-exposure controls and2non-E controls). One captured mover:4178 E-1000 mixed natural/synthetic,82.4→76.9; Dose20→14.5, other pillars/status/route/safety objects unchanged. All18controls unchanged. The>=500 activity census is a bounded cohort, not every potentially affected Vitamin E label. Clean replay manifest a656746f9ae8507d63fcf74b7b8cf6b091d6d455da5b044f264bfc8e4913346f; candidate output029e2e8f82182fd465bd312264a2f25d93ba332fd5e3140a5082cc8bbcd17b45.
- [x] Correct existing Flutter ingredient readers/stack aggregator/legacy dose safety (3553342c). Nutritional totals stay unchanged; UL comparisons consume the pipeline safety_exposure. A malformed present exposure remains unresolved.193affected app checks pass; make analyze reports no issues. No app-side form math or score recomputation.
- [x] Independent final review accepted pipeline27d9b751/app3553342c with47checks passing and no remaining actionable findings; vitamin_e_review.md records the receipt.
- [x] Local corpus checkpoint at103b699e:527passed24declaredoptional skips136.74s; skip guard passed. An earlier attempt terminated with SIGTERM near completion and is retained as an interruption, not a pass or assertion defect.
- [x] Combined pipeline CI37214645369 passed on exact103b699e (all4groups), covering final runtime/data source27d9b751.
- [x] Whole-app CI37214557986 passed at3553342c/draftPR92:analysis,CI-scoped tests and changed-Dart formatting green. Bundle/device/candidate-release acceptance remains separate.
- [x] Exact final branchCI37215506742 passed atfed96040; pipeline main fast-forwarded/pushed tofed96040 and app main3553342c on Sean's explicit instruction. Runtime/data unchanged from green103b699e/local; integration complete, release validation remains open. Earlier reason-only CI37210341807 passed at e6937db5; final combined CI37214645369 at103b699e separately validates the Vitamin E extension. The initial local queue was stopped before source edits. After the main lane's exclusive full process exited, the audit local checkpoint ran and passed as recorded above; no competing broad suite was started.
- [x] Both reviewed branches merged/pushed to main: pipelinefed96040/app3553342c.
- [ ] Run fresh corpus from Clean through Enrich and Score, rebuild/check the app catalog, then freeze and review the new candidate. Existing6ea851dc release artifacts do not validate this correction. No external publication or app-main mutation occurred.

Owner: scripts/unit_converter.py::UnitConverter.convert_nutrient/_ul_exposure_amount; scripts/enrich_supplements_v3.py existing RDA/UL producer and canonical nutrient aggregate; Flutter IngredientRowFields UL readers, StackNutrientAggregator and DoseSafetyHelper. Evidence: live NIH ODS Vitamin E factsheet, source-linked failing regressions, focused receipts, committed frozen replay and consumer tests. Will NOT create: a second form detector/converter, field, clinical registry, scoring/status policy or app scorer. Receipts: /Users/seancheick/pg_quality/claude_dose_safety_audit_20261004/.

Next unchecked work: fresh candidate validation after completed review/CI/local/integration and gold coverage for blends/missing data, scoring controls, strain identity and explicit recalls. The three Copper label corrections still need recorded human owner sign-off. A passing226-case benchmark does not close the remaining families or final release.

- [x] Cleanup complete: removed own merged pipeline audit and app consumer branches locally/remotely; removed merged pmc-idconv-retry/sida-cui-release-gate branches locally/remotely and superseded local master-plan-audit branch (preservation receipt already in this ledger). Archived the managed pipeline audit worktree with recoverable snapshot; removed own app worktree after committed-source checks and saved handoffs in durable receipts. Active release lane and independent review worktree were retained.
- [x] Preserve concurrent Claude9f9a391c correction: three Vitamin E gold basis descriptions now state UL-mass arithmetic directly, with activity labelled separately. Numeric expectations unchanged; final named gold benchmark45passed2.82s. This copy-only correction does not change runtime/data fingerprints or invalidate source measurement.


October4 final pre-run integration at main7c5fdb4a (concurrent documentation af83c99d preserved): combined candidate f87abebe contains the reviewed LA-5 source correction and catalog development report owner3b0f10d6. CI37218808877 is green on that exact combined commit; local537/24declaredskips covers final clinical stage source; gate slice60passed. The earlier worktree-only missing-canary checkpoint is rejected and the interrupted CI runs are superseded. Final47 frozen labels unchanged and Q53nine has only the explained264105 mover; no unexplained captured movement. All38Clean/Enrich/Score manifests are stale: Sean's next run is clean,enrich,score --pipeline-only. Remaining clinical coverage, rebuilt-artifact/device and release gates stay open; this is readiness for the next development corpus run, not final release acceptance.
### October 4 — bounded beta pre-run closure

- [x] Sean clarified publication policy: unresolved identity/form products remain withheld; confirmed banned/recalled products still ship BLOCKED with their reasons. A CAUTION warning alone does not exempt an unresolved product. No new public status or publication exception.
- [x] Fresh frozen-raw replay of 47 labels confirms all37 prior-caution form holds remain withheld. Bitter Orange/Citrus aurantium source exclusions are deliberate and regression-pinned; unresolved mixtures, chemical preparations and contradictory source forms are not forced matches. Per-product dispositions are retained in beta_prerun_closure_20261004/held_product_dispositions.json.
- [x] Inspect original catalog drivers for six milder cases:18529/5862/5864 had DOSE_OVER_UL_CRITICAL, including the confirmed Copper unit error;219819/219827/219832 had B0_HIGH_RISK_EXCIPIENT_WARNING_ONLY and a historical high-caffeine flag. Existing source/daily-exposure corrections and advisory-versus-verdict policy explain current outcomes; the original flags establish the drivers, not a reconstruction of every historical numerical UL assessment; warnings remain independently represented. This batch changes none of these six scored/gate records.
- [x] Fix264105 exact LA-5 form lost under Advanced Acidophilus heading in the existing studied_formulas::clinical_strain_identity_from_label owner (58dd0ac9). Require agreeing source species, one fully printed identity, source lineage, no conflicting scientific name/code. Reuse existing designation parser; do not create another taxon parser. Independent review caught abbreviated conflicting species; final regression covers it. Follow-up d52c5500 rejects embedded scientific identities and genus-only source groups; both new edge cases failed before repair.
- [x] Final focused identity/collector/public-artifact slice138passed. Earlier131pass/5optional corpus skips was the source-only worktree slice. Two frozen cohorts47+9:47 unchanged; only264105 moves44.8→59.9, Formulation2.7→13.3/Dose9.1→13.6 under existing identity/disclosure rules. Evidence0 stays0; route/status/safety unchanged. Eight clinical controls unchanged. No magnitude, registry grade, benchmark or safety policy changed.
- [x] Independent live source review: nine NIH source labels match retained rows/servings/statements. Remaining Q53 identities stay honestly unresolved; LA-5 gut Evidence remains zero. PHGG/inulin/XOS/GOS/phage grading/preparation questions remain later clinical-policy gates, not invented positive findings.
- [x] Final measured review accepted d52c5500; exact combined candidate f87abebe CI37218808877 passed all four groups. Local537passed24declaredopt-in skips150.68s; skip guard passed. Gate-only integration changes no stage code/reference fingerprints; focused gate/wiring60passed. Combined source integrated to main; no catalog publication.
- [x] Sean completed Clean→Enrich→Score and strict catalog build on October4 (`batch_run_summary_20261004_173701.txt`), source c1deb2f2:114 current manifests verified. Subsequent DNS release failure and new copy correction are tracked below; this is a completed development run, not final release acceptance.

Owner: scripts/studied_formulas.py::clinical_strain_identity_from_label; scripts/probiotic_measurements.py::label_strain_identity_resolution/_label_designation_tokens; existing cleaner/enricher, scored artifact and build_final_db publication qualification. Evidence: source matrix/callers, fail-first wrapper regression, public scored-artifact regression, frozen47+9 raw-label replays and independent source review. Will NOT create: scorer, parser, registry, status/field, publication exception or numerical policy. Receipts: /Users/seancheick/pg_quality/beta_prerun_closure_20261004/.

Next after the new corpus: build and inspect the candidate catalog/interactions/app, use the integrated cause-based development movement report (with safety exceptions still reviewed), run sequential release/full and real-device checks, freeze manifest and obtain external publication approval. These artifact/consumer checks do not require another corpus pass unless source or provenance actually changes. No whole phase is closed by this bounded batch.


### October 4 — reviewed-zero copy and probiotic source fusion

- [x] Correct the existing shared reviewed-zero explanation: “We reviewed the research but found no qualifying human clinical evidence of benefit applicable to this product.” It no longer denies the existence of human studies. LA-5 combination gut evidence and a different-indication monostrain trial remain recorded, without borrowing positive gut credit. No score, grade, source record, status or policy changed.
- [x] Independently trace both older clinical_matches and newer approved exact-strain study_contexts through the existing probiotic Evidence owner. Both are considered; strongest applicable family wins, rather than adding database totals. Replication groups independent trial families. Verified human legacy summaries retain ownership; approved human contexts can replace signed preclinical-only summaries; suspended legacy review remains held. New strain entries use accepted contexts where eligible, and pending/combination-only entries do not automatically earn credit.
- [x] Fail-first shared-copy regression, public raw-label scored-artifact regression and dual-path/nonstacking regression. Focused owner, precedence and new-strain slice: 272 passed in 4.88s. Real raw Solgar264105 before/after: total 59.9, Evidence 0/20, all other selected score/status/safety fields unchanged; only the explanation differs. Receipts: /Users/seancheick/pg_quality/beta_prerun_closure_20261004/evidence_copy_{before,after}.json. Independent review: no blocker; five independently rerun cases passed.
- [x] Integrated source `d09c6f56` after exact-source CI [37220847507](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37220847507) passed all four groups; local 537 passed / 24 declared opt-in skips in 148.42s, skip guard passed. Final strengthened dual-path check passed. This integration receipt changes documentation only; final corpus, clinical coverage, catalog, device and release validation remain open.

Owner: scripts/scoring_v4/quality_score.py::_EVIDENCE_ZERO_REASON; scripts/scoring_v4/modules/probiotic_evidence.py::score_evidence; scripts/probiotic_measurements.py::effective_strain_evidence. Evidence: current matrix/glossary/callers, source precedence regressions, public raw replay and independent review. Will NOT create: another scorer, registry, status, public field or clinical policy.


### October 4 — validation proportional to correctness risk

- [x] Sean approved removing blanket pre-merge CI waits for small, proven nonbehavioral changes. Updated the existing AGENTS.md Tests owner with one validation table; aligned the scoring rule and scoring-change skill instead of creating a second procedure.
- [x] Documentation/process changes use diff/reference checks. Existing-assessment display copy uses named owner/consumer checks plus a real-product before/after proving underlying decisions unchanged. Tests-only edits use meaningful affected tests. These classes do not require a broad local checkpoint or a CI wait before merge.
- [x] Behavioral pipeline/data changes retain the finished-batch CI/local gates, source verification, measurements and required review. Clinical facts, safety advice, identifiers, applicability, contracts and test/CI infrastructure cannot use the copy exemption. Mixed or unresolved-impact changes use the higher gate. Automatic CI remains enabled; pending results are recorded honestly, independent work may continue, and failures block release/dependent behavior until resolved.
- [x] Reviewed the complete constitution, scoring/clinical rules, scoring/data procedures, current CI workflow and verification runbook; checked the final diff and references. Walked through documentation, LA-5 explanation, an added nonstacking regression, a one-line dose/recall edit, a test-runner change, and a mixed copy/scoring batch: each selects the intended validation class. This batch changes instructions only; no pytest or CI wait is required.
- [ ] Fresh corpus/candidate, clinical coverage and release/device gates remain pending under the original completion plan. This process adjustment neither validates old artifacts nor approves publication.

Owner: AGENTS.md::Tests — evidence: scripts/test.sh/test_profiles.py, .github/workflows/pipeline-tests.yml and existing rule/skill callers. Will NOT create: runner, automated risk classifier, bypass flag, workflow, tracker or release shortcut. No executable, scoring, curated-data, app or CI configuration changed.


### October 4 — magnesium certification matching closure

- [x] Trace both missing Nature Made capsule labels (310116/322551) to omitted “High Absorption” in the source titles. Reviewed the entire Nature Made glycinate-label family; gummy313829 already has a separate reviewed record.
- [x] Live USP page12 HTTP200 confirms distinct capsule/gummy listings; official capsule page and both NIH raw labels agree on200mg magnesium as bisglycinate per two capsules,60 capsules. Added two reviewed DSLD-specific SKU aliases through the existing override owner, with explicit strength/form. No fuzzy thresholds, numerical magnitudes, source dates or clinical policies changed.
- [x] Public normalizer→full enrichment→scored-artifact regression failed before the mappings. Owner/consumer/data slice:513passed,22missing-corpus skips in7.93s (worktree has no corpus). Twelve identity boundaries retain exclusion: wrong strength/form/brand, missing form and unreviewed label ID. Source review in existing research.md.
- [x] Source candidate `cacc8bf6`: six frozen raw labels measured with aligned reference inputs; only the two capsule labels move88.4→93.4 (Verification10→15). Four controls are byte-identical; the other five pillars, routes, statuses and raw hashes stay unchanged. Independent review accepted the identity exclusions and final source-isolated replay. Whole-fast CI37225847766 passed on this exact source candidate.
- [x] Interim implementation is superseded by the approved catalog-wide renewal batch below: one reusable reviewed identity alias replaces both handpicked mappings. Historical six-label/CI receipts remain evidence for the interim only; final integration/rebuild states are tracked below.

Owner: scripts/cert_resolver.py::resolve/_check_override using scripts/data/curated_overrides/cert_verification_overrides.json; scripts/scoring_v4/cert_evidence.py consumes the resolution. Evidence: certification_evidence matrix, production callers, exact data_batch expected-entry check, primary-source receipt and fail-first public seam tests. Will NOT create: second matcher, registry, scorer, policy, magnitude or export field. Receipt directory: /Users/seancheick/pg_quality/certification_match_20261004/.


### October 4 — catalog-wide certification matching and monthly renewal

Owner: scripts/cert_resolver.py::resolve/_check_override; scripts/api_audit/verify_certifications.py::main/build_refresh_candidate; scripts/api_audit/cert_label_registry_audit.py::main; scripts/scoring_v4/cert_evidence.py remains the only numerical owner. Evidence: matrix, production callers, failing boundary tests, official-source responses and full-corpus census. Will NOT create: second matcher/registry/scorer, public fields, numerical magnitudes, policy or release shortcut.

- [x] **Implemented:** reusable source-reviewed Nature Made title equivalence, including an unseen label ID; exact source-corroborated consumer-brand trade designations for manufacturer-listed products; refreshed reviewed-alias identity checks; non-product scope exclusions. Preserve strength, form, preparation, population, named additions and ambiguity guards.
- [x] **Implemented:** all-product census, including held and no-claim labels; per-entry outcomes, input fingerprints and override audits. Initial baseline includes15,421 unique labels and14,220 without recorded claims. Final refreshed-registry delta is pending below.
- [x] **Implemented:** candidate-only nine-source refresh, raw response receipts/hashes, completeness/failure guards, original dates for preserved sources, stable authoritative IDs and withdrawal/migration reports. Correct NSF endpoint, NSF variant-ID collisions, IFOS/Informed deduplication and BSCG product-slug merging. Reject malformed listing/detail responses and erasure of prior lot evidence.
- [x] **Implemented:** all nine complete snapshots applied to the candidate; all six existing rejected NSF mappings preserved across identity splits. Additional IKOS/IAOS/IPRO fetchers produce evidence-only candidates outside production pending program policy. Review all23 recognized programs and ISURA availability in existing research.md. Correct misleading NSF455/GMP+/Labdoor/TGA descriptions without changing capabilities or points.
- [x] **Implemented:** recurring Codex task monthly-certification-audit-and-renewal, first day of each month9a.m. America/New_York; same manual pre-release procedure in docs/runbooks/verification-gates.md. Sean explicitly authorizes independently reviewed existing-policy main integration; new policy/identity conflicts stay held. No catalog/app publication.
- [x] **Measured:** final census15,421labels/116unchanged inputs/0errors:806→907verified products;117labels change verified programs (110additions,7removals), plus4record-only relinks. Raw replay123labels captures all119program-set changes (including2previously historical non-awarding ConsumerLab rows) plus4controls. Eleven totals increase only through Verification;112totals unchanged. Nature Made310116/32255188.4→93.4; five BulkSupplements creatines91→100 under unchanged scoring rules. All other pillars, safety/dose gates, statuses, routes, readiness dimensions outside Verification and catalog dispositions remain unchanged. Seven Garden of Life CBD labels lose now-absent NSF Sport matches but retain suppressed_safety and their warnings; this is directory absence, not a claim that NSF formally revoked certification. Nine ambiguous certification identities and3preexisting missing Garden of Life aliases remain non-awarding. Full cause/score receipts are retained.
- [x] **Reviewed:** fresh independent review reproduced three source defects, then accepted all fixes with40checks and verified response/source/candidate hashes. Combined owner/data/ratchet slice462passed; source/fetcher/metadata slice165passed18declared skips; final local537passed24declared optional skips170.19s, skip guard passed. Whole-fast CI37230228086 passed all4groups on exactsource d4f9c945. Exact data_batch entry checks pass for registry, override and claim-note files. No numerical configuration, capability, maximum or policy changes.
- [x] **Integrated:** source d4f9c945 and measured/reviewed receipts dea7188e fast-forwarded/pushed to main; origin/main containment verified. Deleted local/remote codex/certification-match-audit and archived its managed worktree after removing only owned temporary links/reference copies. Current-source CI remains37230228086; final integration receipts are documentation-only and require no duplicate broad checkpoint. External catalog/app publication remains separate.
- [ ] **Release-validated:** certification source is now present in the October4 rebuilt catalog and fresh census; Nature Made93/Excellent verified. Final clinical/app/release acceptance remains open; the later note-scope correction and checkpoint status are tracked below.

Receipts: /Users/seancheick/pg_quality/certification_renewal_20261004/ and /Users/seancheick/pg_quality/cert_refresh_20261004_all/. Existing missing Garden of Life NSF reference remains explicitly reviewed/held; source absence does not authorize a replacement alias. Pending program interpretations and identity exceptions receive no new credit.

### October 4 — shared citation reuse and release429 bottleneck

Owner: `scripts/api_audit/pubmed_client.py::PubMedClient` (existing transport/cache);
`verify_all_citations_content.py::fetch_articles/verify_file/baseline_failures` and
existing backed-study, interaction/Bookshelf, depletion and IQM consumers. Evidence:
production release callers, fail-first cross-batch regression, owner/consumer tests,
official NCBI converter documentation and saved live source receipts.
Will NOT create: a second verifier/cache/clinical registry, cached claim approval,
new numerical policy, changed backlog exemptions or release bypass.

- [x] **Implemented:** full article records reused by PMID across batches/processes;
  PMC identity mappings use that same disk cache and current official endpoint.
  Atomic serialized persistence, bounded429/5xx retries, current-context checks,
  existing14-day expiry and failure-closed refresh retained. Duplicate direct network
  paths removed from the content, Bookshelf and depletion-presence gates.
- [x] **Measured:** supplied run successfully built15,421pipeline blocks and15,154
  catalog rows, then release failed on56PMC citation occurrences/53distinct IDs.
  Live probe resolves all53 in2requests/7.46s; warm repeat0requests/~0.05s.
  Current-source content checks:54matches,1partial,1already-known mismatch,
  0new mismatches,0unresolved. Known omega/niacin mismatch stays in the backlog;
  successful retrieval is not clinical signoff.
- [x] **Implemented reporting:** JSON retains every finding; console separates new
  mismatches, unresolved retrieval and known backlog, with cache/live counts.
  Old251backlog count was not251new failures and remains clinical work.
- [x] **Reviewed/measured:** full diff and owner/consumer contracts inspected;146focused
  checks pass before expiry pruning,52post-pruning checks pass with3local I/O scan
  timeouts explicitly rejected. Complete production citation gate passes;1,965
  occurrences,0new mismatches/0unresolved,252known backlog. Warm complete repeat
  1.57s/0live requests/identical decisions. Expired-cache cleanup344MB→39.6MB;
  renewed valid records later bring cache to55.8MB. No clinical signoff or publication.
- [x] **Integrated:**2cb0f9e1/99ea3f6d merged and pushed to main, origin containment
  verified. Final whole-fast CI37235340132 passes all4groups on exact source99ea3f6d;
  first checkpoint37233972615 also passed2cb0f9e1. Receipt-only documentation does
  not require a duplicate broad checkpoint. No corpus or publication started here.
- [ ] **Release-validated:** final rebuilt candidate and release checks remain open.
  Audit-client imports are included in all three stage fingerprints; this change
  invalidates existing stage stamps despite unchanged scoring/reference data. Combine
  with the already-required certification rebuild in one main-based pipeline-only run.

Receipts: `/Users/seancheick/pg_quality/citation_cache_20261004/`.

Citation lane cleanup: local/remote `codex/citation-cache` deleted after verified
main containment; managed citation worktree archived. Main is the only local/remote
branch. Unrelated detached catalog-form-remediation worktree is preserved.


### October 4 — fresh corpus validation and species-fallback copy correction

Owner: `pipeline_freshness.py::stage_freshness_issues`, `build_final_db.py::build_detail_blob/_derive_form_note`, `ingredient_quality_map.json::forms.consumer_note`, existing certification census and `release_safety/catalog_diff.py::diff_catalogs`. Evidence: completed run log, 114 manifests, actual SQLite/blob comparison, fresh all-label census, fail-first owner regression and production blob before/after. Will NOT create: scorer, parser, registry, public field, numerical policy, approval receipt or release bypass.

- [x] **Measured:** Sean's `batch_run_summary_20261004_173701.txt` completed Clean/Enrich/Score and strict snapshot on source `c1deb2f2`: 38 datasets, 114 current manifests, 15,421 pipeline inputs, 15,154 exported, 267 held, 73 BLOCKED, zero export errors/contract failures. GitHub DNS failure stopped the subsequent release-base fetch; this is not a scoring/citation failure. External publication was not performed by this audit.
- [x] **Measured:** catalog generation `2026.10.04.225231`, core hash `e412ae0d95d16733812fa958d124359cc0a89d176f4bf47ed1498951004bec61`. Both Nature Made labels310116/322551 now ship93/Excellent, Verification15; safety unchanged. Fresh census covers15,421 labels,14,220 without claims,907 discovery matches and9 ambiguous identities. Discovery deliberately applies the existing additional no-claim strength guard; its count is not every claim-driven certification award.
- [x] **Measured:** compare against preserved earlier development bundle:15,154 shared,0 added/removed,18 whole-score movers (14up/4down),0 safety-verdict transitions,0 score-status/blocking-reason changes. Thirteen movers are Verification-only; three Vitamin E Dose-only; Solgar264105 and Heart Health328803 change strain-related Formulation/Dose. The raw LA-5 score59.9 is shipped60; Evidence remains0. Full per-product pillar receipts retained; aggregate owner attribution does not close clinical or release review.
- [x] **Implemented/checked:** reproduced Heart Health328803 printing NCIMB30242 while the IQM fallback note claimed no strain was printed. Correct44 shared species-form notes to describe the scope of the catalog form rather than the printed label. No scores, grades, aliases, IDs, study records, reviewer decisions or source selection change. Regression failed before repair;47 named owner/consumer checks pass. Production blob comparisons on328803/264105 show only form_note/form_note_preview changes on328803 and no changes on264105; every other field is identical. This is existing-assessment display copy under AGENTS.md's proportional validation rule, not clinical regrading.
- [x] **Local app preparation:** importer dry-run and real local import pass supported schema, projection, checksum, SQLite integrity/count and embedded-manifest gates. Preserve the prior dirty assets in the durable receipt directory. Local catalog bundle updated; existing dirty interaction assets preserved. No Supabase upload, app release, app-repository commit or device-rendering claim.
- [ ] **Release-validated:** first release-rung attempt failed honestly on stale app bundle. After local import, preflight passed; the unfinished broad checkpoint was deliberately stopped after the new copy defect was reproduced. It is CANCELLED, not green. Full backstop was not started. Source-copy edit now invalidates all114 reference-data stamps; no restamping/bypass. Combine the necessary Clean→Enrich→Score refresh with the remaining bounded clinical/source work, then rebuild catalog/interactions/canaries and run one sequential final checkpoint. Do not ask Sean to rerun for this intermediate copy edit.
- [ ] **Still open:** clinical applicability/coverage queues, complete movement classifications, interaction freshness, device/nutrition rendering, frozen release manifest, final release/full checks and exact-candidate publication approval. No whole phase is closed by this audit.

Receipts: `/Users/seancheick/pg_quality/citation_cache_20261004/postrun_*`; pre-import assets in `app_before_import/`. This source-only correction is not yet present in the imported candidate blobs. Later source-review work below does not restamp that historical catalog.


## October 4 — clinical readiness and dual-use owner batch

Baseline `b0af340a`; candidate source `c1a31c79` (`dbaebe3f`, `37e83e4d`, `c1a31c79`). This closes three confirmed defect classes; it does not ratify new clinical grades or declare the entire clinical queue finished.

- [x] **Implemented:** Readiness consumes the existing resolver's verified nonpositive literature determinations and exact label-owned concluded native strain reviews. Species/stubs, unverified records and identity-insufficient subjects remain pending. LA-5's reviewed zero is complete, not missing research.
- [x] **Implemented:** Evidence readiness uses the canonical subject provider and shared whole-label roles; undosed named blend children cannot silently disappear. Structural strict rows remain outside individual Evidence while retained for Dose; Dose keeps strict exposure requirements.
- [x] **Implemented:** One excipient decision serves row signals and scoring selection. Source membership/recognized identity, canonical excipient/descriptor/nutrition roles and nutrition-rollup protection govern purpose; amount alone cannot demote an active ingredient. Genuine inactive/excipient rows remain excluded.
- [x] **Implemented:** Tesnor notes correctly describe the older-men trial's primary symptom score and secondary hormone/strength outcomes, preserving exact-formula scope, numerical grade and200–400mg benchmark. D23's obsolete unmatched-header description is superseded.
- [x] **Implemented:** Spirulina summaries retain the HIV population/null disease markers and pediatric nephrotic-syndrome within-group comparator. Existing aggregate grade remains a clinical-review obligation; this patch does not ratify it.
- [x] **Measured:** Active additive-flag census covers5,770rows;726flag decisions differ across579products. Source-frozen29-label replay has no score/status/route changes. Final591-label capture on `f521aef0`:14score movers,1route change,0status/safety-gate/Dose-risk changes,0unexplained material movements. Twelve restore existing Spirulina Evidence,46707 restores existing VitaminC Evidence,17226 uses the existing fiber route/denominator after active pectin is retained. These owner fixes do not ratify the open Spirulina clinical grade.
- [x] **Reviewed:** Fresh read-only reviewers reproduced source ownership, pending-review, real-excipient and structural Dose boundaries; their detected defects were corrected before acceptance. Initial CI exposed3additional classes: legacy active-source compatibility, recognized-excipient identity/safety retention, and a stale synthetic confidence pin. Fail-first fixes and final review close them;345defect-class checks,124final owner/source checks and41archetype checks pass. Local537passed/24declared opt-in skips; two changed clinical entries pass strict existing citation-owner check on9references.
- [x] **Integrated:** Source `f521aef0` passes exact-candidate CI37248345191(all4shards), final local gate and independent review; fast-forward integrated/pushed on main with the documentation-only progress update. Own temporary branch/baseline removed after containment. Final release validation remains separate.
- [ ] **Release-validated:** Current source needs a fresh combined rebuild and artifact/device gates. Do not restamp the October4 artifacts or request an intermediate corpus run while remaining output-changing clinical decisions are unfinished.

Durable receipts: `/Users/seancheick/pg_quality/clinical_role_completion_20261004/`. Owner: `assessment_readiness.py::evaluate_evidence_assessment`, existing resolver/subject/strain owners; `SupplementEnricherV3::_compute_excipient_flags`; existing `BRAND_TESNOR.notes`. Will NOT create another subject list, classifier, Evidence/Dose policy, registry, status or numerical grade. Phase2 demonstrated dual-use source correction is complete; final Evidence-subject census remains open. Existing Spirulina aggregate grading, counts and general Healthy Aging applicability require clinical review before release.


## October4 — bounded clinical reviews and complete source-subject census

Owner: existing `get_evidence_subject_rows`, `classify_ingredient_roles`, `clinical_applicability.assess_clinical_applicability`, `evidence_resolver`, curated clinical/literature registries and `measure_catalog_shadow_completeness`. Evidence: source matrix/callers, fail-first owner/clinical regressions, exact primary content, independent reviews and frozen raw inputs. Will NOT create another registry, matcher, classifier, subject list, scorer, public field, grading magnitude or release approval.

- [x] Complete per-entry remaining bounded reviews: plant ALA, flaxseed preparation, PHGG/Sunfiber, inulin/FOS, XOS/PreticX, GOS/Bimuno, PreforPro, Spirulina and the eight unresolved Q53 source identities. Completed review does not imply positive clinical points or known missing strain/preparation.
- [x] Correct shared preparation/outcome applicability and overstated source facts through existing owners; preserve undosed member Evidence review and strict separate Dose exposure. Three backed records and six literature records changed; exact batch checks pass.
- [x] Independent owner/clinical reviews accepted after repairing undosed-member filtering, source citation titles, phage endpoint roles, historical search provenance and source-specific purpose. Whole powder is not an extract; null HIV/pediatric descriptions do not become supported purposes.
- [x] Targeted owner/source/consumer checks338passed; final printed-child lineage slice218passed. Final source380e1713 local537passed/24declared opt-in skips in159.18s; skip guard passed. Final marker/parent/enzyme owner slice297passed. Bounded existing verifiers:17backed PMID-entry claims and12literature studies, no title/content/not-found flags, corrections or retractions. General citation verifier does not cover these separately owned registries.
- [x] Complete the all15,421 frozen-raw subject census and2,101 affected/control raw-label measurements; retain every disposition and explain incomplete subjects. Census is an audit using current Clean/Enrich owners in memory, not a stage rebuild, final catalog or publication.
- [x] Integrate the exact validated source after whole-fast CI; source380e1713 and measured/reviewed register31f5e01b fast-forwarded and pushed to main. Runtime/data fingerprints equal accepted source; own local/remote branch and baseline checkout removed after origin containment, unfinished Claude lane preserved.
- [ ] Release-validate with one necessary combined Clean→Enrich→Score rebuild after remaining source fixes, then catalog/app/device/release/full checks, manifest and exact-candidate approval. No old-manifest restamping or interim pipeline run.

The older stored-enrichment diagnostic exposed55 canonical buckets with pending identity/literature states, including ALA now reviewed. It is not a fresh-candidate count. Independent classifications identify further owner joins and preparation/source risks; they must remain visible in the final census/LEDGER, not be relabeled completed positive or absent research. Existing clinician-held form grades and unknown retail/trial correspondence remain explicit.

Current candidate `380e1713` also fixes confirmed preparation-only exposure prerequisites, provider-anchor printed-child linkage, omitted literal Chicory root Fiber scope, and provided-marker promotion through existing owners. A failing real-shaped lineage regression and raw251338 boundary guard supplement the earlier synthetic coverage. These are systemic owner repairs; The accepted2,101-label immutable replay has85 total movers (11up/74down),27 quality-tier crossings and zero status/safety/DoseSafety/completeness changes. The only profile change is232485 botanical→generic_iqm; its main route stays generic. Every movement has an independent per-ID source classification, with zero unexplained movements. Whole-source census is complete with102,281subjects,15,101resolver-complete/320partialproducts;340subjects across58canonicals remain pending, with individual source/disposition retained.

Broad-checkpoint correction:8182a183 failed three independently reproduced classes (a stale undosed-Evidence test, overridden original source exclusion and iodine source-form loss). Candidate380e1713 preserves original source exclusions, permits provider-owned undosed/anchor lineage only as intended, and restricts marker handling to the declared providing/provides/supplying relation through one existing-owner helper. Typical source qualifiers and supplied enzyme potency remain named forms. The stale test now pins exact child source, unknown exposure and absent clinical benchmark; four mutations prove its guard strength. Final1,019owner tests pass. Superseded captures and cancelled partial censuses are not acceptance receipts.

Completed-source checkpoint: `380e1713` passed all four `pipeline-tests` groups in [run37257597295](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37257597295). Final local537passed/24declared opt-in skips (159.18s), skip guard passed; final owner/consumer slice1,019passed. Final movement review: `clinical_completion_20261004/final_movement_review.md` and `.json`. Source8182 failed and is superseded; it is not the accepted checkpoint.

Final census on source380e1713:15,421labels (15,412DSLD +9manual submissions),102,281subjects;15,101resolver-completeproducts/320partial. Dispositions: authority50,104; reviewed clinical27,300; reviewed null445; no qualifying human evidence3,627; not efficacy relevant8,282; reviewed research with applicability unestablished12,183; literature resolution required337; identity insufficient3. The first six are concluded resolver determinations, not proof of positive efficacy, universal material identity or fresh independent review of every registry entry. Full output retains every source row and reason. Two malformed raw labels250356/312659 remain existing Clean holds, not successful clinical negatives.

Census SHA-256 `9d42576e9b2323ac7fcc1efceae4082c16898ff0dc3680e7d890b23cdca69869`; immutable manifest `b0852397fa228dd6d85b79c900111581b6894c254e152f9b00cdea6257583996`. Receipt directory `/Users/seancheick/pg_quality/clinical_completion_20261004/`; `accepted_subject_census.json`, `accepted_census_summary.json` and independent `final_census_review.md/json`. Newly surfaced oil/source/preservative groups remain explicit source-role/preparation review tasks; absence of an Evidence record is not a no-human-research determination.

Q53 count boundary: the eight researched labels resolve as `research_present_applicability_unestablished`; LA-5 resolves as `no_qualifying_human_evidence`. These are concluded owner determinations, so those nine are not counted in the340pending subjects. Missing exact strain/trial correspondence still prohibits unsupported credit; concluded applicability is neither identity equivalence nor a new catalog-wide hold.

Independent final census acceptance:30,858integrity checks and11representative source/provider/resolver reproductions pass; all340pending subjects/58canonicals classified, zero unclassified. All91ALA subjects now have the existing reviewed clinical determination. The final six new groups are respectively exact-compound/preparation research (beta-caryophyllene), mineral-source/authority linkage (DCP), demonstrated active VitaminC/preservative source-context correction, per-label olive-oil purpose/preparation, RiceBranOil multi-component Toco-Rich anchor and varied sunflower lipid/carrier/combination contexts. No universal incidental demotion, borrowed blend dose or new clinical negative follows.

Integration: source380e1713 plus documentation-only31f5e01b are pushed to main and origin containment verified. Own `codex/clinical-applicability-census` local/remote branch and baseline checkout deleted after preserving owned scratch receipt; unfinished `claude/gold-benchmark-blends` and unrelated detached checkouts/app assets preserved. No duplicate broad checkpoint for receipt-only documentation. Actual114stage manifests (38each Clean/Enrich/Score) are stale; source will need one combined rebuild after the remaining output-changing owner fixes. No corpus job, catalog publication or release was started.


## October 5 — remaining source corrections and exposure decision packet

Owner: existing enhanced_normalizer preparation/printed nutrient identity, enricher IQD identity, IQM collagen/Acacia and botanical Triphala owners. Evidence: matrix/glossary/callers, fail-first source regressions, live primary content, immutable 123-label replay and independent review. Will NOT create a scorer, registry, public field/status, new grade, policy or release bypass.

- [x] Implement source corrections: restore active qualified VitaminC while preserving qualified VitaminA/UNII and inactive preservatives; remove NEM-to-purified-peptide aliases; correct UP446 companion/preparation wording; prevent explicit Triphala extracts receiving powder identity and fatty-oil blend headers receiving volatile-oil identity. Preserve raw members, amounts, actual powders and sole-purpose formula Evidence.
- [x] Measure final source `8084ca71` against dfeff692 on 123 frozen labels: three reason/readiness payload changers 178674/184942/267347; no numerical pillar/total, status or route movement. This subset does not refresh the 102,281-subject census.
- [x] Prepare the four remaining Evidence-to-Dose exposure decisions in the existing transfer README. Zinc retains nutrient/UL/Safety ownership; D-mannose and D-aspartic-acid null exposure cannot become positive benchmarks; white-kidney-bean lowest studied amount is not a proven efficacy threshold. Existing amount gates remain intact pending equivalent Dose ownership and approved treatment.
- [x] Validate/review exact source `8084ca71`: all four CI groups 37268235385 pass; local: 537 passed / 24 declared opt-in skips in 149.77s, skip guard passed; independent source/movement review accepted.
- [x] Integrate with Sean's October5 authorization: PR62 merged as115b30eb; origin/main contains validated source8084ca71 and documentation158ef4da. Temporary branch/worktree cleanup recorded in LEDGER.
- [ ] Complete broader exact-preparation clinical coverage and final artifact/app/release validation. The October5 four descriptive transfers are implemented, measured, reviewed and validated (Phase1 box above); stage fingerprints require Clean. Sean performs the combined pipeline run. Generic WKB and remaining clinical/preparation uncertainty stay explicit; no intermediate corpus run or old stamp rewrite.

The 53/70 phase count remains unchanged. The 58 classified pending groups are not universally closed by identity containment. Source receipts and checkpoint results: existing pending-items LEDGER/research and `/Users/seancheick/pg_quality/clinical_source_continuation_20261005/`.


### October 5 — Claude blend audit, integrated

Independent audit of `a9bd0a3e` on current main found and repaired four source-owner defects: recursive hidden/NP descendants incorrectly yielding full disclosure, known stimulant doses incorrectly labelled undisclosed, distinct same-name blend parents collapsing together, and downstream Transparency deduplication undoing source separation. Behavioral source `fcb6a613` has fail-first regressions and fresh-context review; 537local checks pass; exact CI acceptance is recorded in the existing LEDGER. Frozen147-label raw replay reproduces107 score movements and seven safety verdict changes from current main. The audit repairs themselves affect only three payloads, with no numeric pillar, total, safety or scoring-status changes from integrated Claude. This is a bounded blend/missing-data gold contribution, not complete clinical, gold, candidate or release validation. Master count remains53/70. PR63 and isolated-fixture repairs are integrated on main `c67600da`;34named source/role boundary checks pass. Remaining clinical/amount-owner closure precedes the single necessary rebuild from Clean, which Sean will run.

### October5 — approved transfers and uncertainty refinement

Accepted runtime e79d8cff plus test-only refinement164a8e99, PR64. All4CIgroups37338107501 green (19,377pass/183declaredskips), local537pass/24declared opt-in skips; independent review accepted after clove extract identity and source-review repairs.183 immutable raw labels show10 explained Evidence-only score increases and zero Dose/status/captured Safety movements. Option1 preserves16/22 and the denominator, with source-authored uncertainty/reference facts; no new public Coverage score. Phase1 live-transfer box is closed, main checklist54/70. Broader Phase3 clinical coverage remains open. Final stage audit requires Clean for all38brands; Sean runs the pipeline himself. No corpus run, catalog refresh or release performed. See the current LEDGER for source, checks and limits.

### October 5 — final source-role remainder accepted

Final candidate0123889b extends the existing canonical identity/normalization and converter owners. Shared literal preparation proof prevents generated aliases or generic taxonomy from supplying isolated marker, extract or extra-virgin specificity. Exact declarations remain retained. Whole-matcha research is recorded as applicability-unestablished without positive credit or a dose benchmark. The additional VitaminE root defect is fixed at the converter/activity seams, preserving non-alpha physical masses while prohibiting alpha nutrient/threshold credit; conservative safety bounds stay separate. Approved16/22 uncertainty fallback and denominator policy are unchanged.

Frozen310-label final measurements have four explained numerical movers (two MicroDefense wrong-species Evidence corrections, OatFiber specificity correction, VitaminEComplete8 genuine-alpha Dose/source-role correction). No score-status/route/subroute changes. All noninteraction warning blocks and product highest severities remain unchanged; interaction name/activity changes follow existing owners and authored unknown-form policy. Independent review accepts finalsource. Exact finalCI37356260687 all four groups green, final local537passed/24declared skips, plus focused regressions/source verification. Execution LEDGER records failed intermediate candidates, fixes, immutable hashes, cause review and integration.

Phase2 is now18/18; overall55/70. Phase3 preparation/formula/route/purpose clinical holds remain explicit. All38brands have stale Clean/Enrich/Score fingerprints; earliest requiredClean. Sean runs one Clean→Enrich→Score pipeline-only pass after integration. Fresh corpus determination coverage, catalog/interactions, app/device, release/full and publication gates remain open; no pipeline or release was run here.

Integration receipt: PR65 merged as904597da under Sean’s authorization. Origin/main contains exact tested0123889b; all436 captured source fingerprints match. Own temporary branch/input mounts removed and managed checkout archived recoverably. Source integration is complete; current corpus, catalog/app and release validation remain open.

### October 5 — completed corpus and post-run validation

Sean's14:57:37 Clean/Enrich/Score batch completed37brands plus Product Submissions:38stage chains,15,421products per stage and114current source manifests at f6357167, with owned-file checksum verification. The default invocation continued into snapshot gates and stopped on one obsolete18141partial-assessment fixture before publication. Existing ALA review and assessment owners support complete with unchanged60.3score/zero applicability-unestablished Evidence; the existing freezer corrects that single status pin and all36snapshots pass.

Post-run inspection also found shared Transparency copy inferred hidden amounts from blend presence. Reviewed display fix9d023a6b consumes the existing B5 disclosure facts used by the fact display, including waived/consolidated penalties and missing-fact controls.104named checks pass; all15,421headline comparisons change210wording cases only. All310accepted-cohort numerical pillars/totals/status/routes and complete warning blocks agree with the accepted source. The32individual warning decision/source-fact table is saved in `/Users/seancheick/pg_quality/post_pipeline_20261005/warning_32_decisions.md`.

Sean approved integration and Score-only regeneration; PR66 merged asf57ea263, containing exact source9d023a6b. Clean/Enrich remain valid. Strict reachability checks15,421products with zero findings. Fresh manifest-owned Enrich resolver census has102,175subjects,15,159complete/262partialproducts and278pending subjects across55groups (275literature/3identity). This establishes artifact determination counts against verified provenance, not broad clinical approval; the census retains its stored-Enrich diagnostic/release-unvalidated scope. Score-only refresh completed across15,421products:206Transparency reasons and timestamps changed; all numerical/status/readiness/route/safety values and the310accepted clinical warning payloads are unchanged. Local catalog/interaction and app reader/widget checks passed, but the candidate is superseded by a confirmed shared conversion defect: complete-name conversion matching and authored mass-scale composition are fixed on codex/clinical-conversion-validation, measured on561frozen raw labels (twoNMN readiness recoveries and onecholine active-moiety correction; no safety-gate or clinical warning-block changes). Fresh-context review accepted with no material findings. Combined checkpoint/integration, regenerated candidate/device validation, release/full and publication remain unchecked. Canonical catalog comparison also retains47unapproved safety exceptions for source/cause review before publication. Master remains55/70; a completed corpus and focused display tests do not close a combined release deliverable. Integration/exact-source/results are maintained in the execution LEDGER and current handoff.


The local catalog trace also found duplicate caffeine parent/component totals and unsupported whole-blend caffeine mass. Fix `fb91849b` reuses existing physical source rows and shared lineage/mass reconciliation; every intermediate subtotal must reconcile. Public regressions fail first, final owner slice passes 211 checks, and fresh review accepts the correction after 13 targeted guards. The final 287-label capture changes 47 outputs: 15 false caution removals, nine restored hidden-dose cautions, 20 corrected signals with caution retained and three elevated→moderate signals. Scores, pillars, scoring statuses and routes remain unchanged; all 287 clinical-warning payloads match. Another 52 frozen controls show zero output changes. Final source repeats all three frozen cohorts with identical preceding candidate outputs; native artifacts differ only in scoring timestamps and all clinical-warning payloads match. Local checkpoint passes 537 checks / 24 declared opt-in skips; exact-source whole-fast CI [37384808424](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37384808424) passes all four groups (19,521 checks / 183 declared skips). Main integration awaits Sean. Actual fingerprints require regeneration from Clean. Master remains 55/70; publication is unapproved.


### October 5 — final194817 run and candidate acceptance

Sean's final run completes38datasets/15,421products per stage with114fresh manifests at9f726a8f. Isolated catalog2026.10.06.013007 has15,149products/blobs,272quarantines and zero export/contract errors. Core SHA173f4e2953a692bc9d3ec00eeb5d4ec08046a49c335932dc583ae2d52212669b; interaction output is byte-identical to the verified132-record source. All800measuredlabels retain exact numerical/status/route agreement and310accepted clinical-warning payloads agree. Native15421comparison has51explained changes (3conversion/48caffeine), no unexplained new deltas. Diagnostic resolver102,175subjects/15,159complete/262partial/278pending55groups remains diagnostic; broader clinical coverage is open.

The62catalog safety exceptions preserve the prior47plus exactly15corrected falsecautions. All37warned removals retain identical identity holds; approval fields remain blank. Candidate hashes and population/movement reports close exactly two Phase7 deliverables;57/70complete. No combined release/device/publication box is closed by these reports.

Test-only acceptance correctiona5560b14 routes dashboard/UL/form/label artifact consumers through the existing release_artifact_paths owner. Six fail-first regressions reproduced stale-live selection;13path/regression checks and66affected candidate consumers pass without changing clinical assertions or runtime fingerprints. That test-only correction did not invalidate runtime artifacts. Release124tests pass and subsequent source/reachability/citation gates complete. Fullbackstop:22,223passed/45skipped/10failed; classified as two production ownership defects and eight obsolete expectations. Shared compound-alias and merged-serving parent fixes are implemented with fail-first tests and focused controls; final frozen660measurement and fresh independent review accept10explained movers with all660safety/dose-safety payloads unchanged.132affected/control clinical-warning blocks and ingredient-safety payload multisets match. Combinedlocal537passed/24declared opt-in skips; b48CI failed one test-only alias-guard ownership class (three other groups passed); the shared source-form guard correction passes55owner checks/freshreview6guards, with unchanged runtime. Final completed-sourcefe504f5a CI[37410974695](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37410974695) passes all4groups:19,533checks/183declared skips; every skipguard passes. Runtime/reference hashes exactly match the accepted b48measurements/localreceipt; later documentation-only updates need no duplicate broad checkpoint. These runtime fixes supersede the candidate fingerprints and require one new Clean→Enrich→Score after integration; do not restamp the completed run. Host app reader/widget2passed and real connected-screen9passed (eightlabels including light/dark and nutritionfacts); native simulator is blocked by existingMLKit architecture/Rosetta availability. Original dirty app assets are restored; physical-device install is unapproved. PR67 merged into main as `a845c895` on October 6 after Sean approved integration and cleanup; publication remains unapproved.

Owner: existing release_artifact_paths, build_final_db/release_catalog_artifact, catalog_diff and appCoreDatabase/detailBlobProvider/ProductDetailV2ConnectedScreen — evidence: matrix/glossary/caller search and actual candidate consumer probes. Will NOT create: another path/scoring/clinical owner, publicfield/status, registry, approval shortcut or app calculation. Current receipts: /Users/seancheick/pg_quality/post_pipeline_20261005/final_run_194817/; execution state remains in the existing LEDGER and handoff.

Local app packaging verification retains the real published-interaction pin blocker (published f5cb versus candidate8efb); no pin or release approval is forged. Test-only calcium/iron QuickCheck canaries follow current curated Moderate→caution behavior, with warning IDs retained; appbranch6eb0a4de. Pairedcandidatefocused48passed/onepublished-pin failure; analyzerpasses and fullapp3754passed/one samepin failure. All four temporaryappassets restoredwithSHAproof; hostconnected9cases pass. Native device acceptance and publication remain open. The two new ownership fixes and the required post-integration corpus pass are tracked in the existing execution LEDGER;57/70 remains unchanged.

Unsigned local iPhone compilation succeeds; all four packaged database/manifest checksums match the staged194817candidate and original app assets are restored. This proves compilation/packaging for that development candidate, not actual phone rendering or freshness after the two new source fixes. Integration is complete. One Clean→Enrich→Score regeneration, renewed catalog/release/full checks, actual-device validation and publication approval remain open.

October 6 current acceptance register: PR67 is integrated as `a845c895`, its temporary branch is removed, and main `9d405e6a` passes automatic CI37412232301. Sean’s final002121 run completed all38datasets/15,421products per stage; all114 manifests were fresh for that source. The isolated catalog2026.10.06.060931 contains15,150products/blobs,271contract quarantines and no export errors. Its core/blob reader checks cover all15,150 products and13 connected screen cases pass. Fresh interaction inputs verify132/132 curated rules and reproduce the prior candidate8efb artifact exactly. No publication, app import or installation occurred.

Supplemental full-catalog movement review identified two production defects: nested identity anchors inherited the container’s taxonomy/forms instead of the selected child’s printed provenance, and profile reconciliation added overlapping descendant constituent amounts as if they were independent portions of a fully disclosed blend. Fixes `0cd822e0` and `2521aea6` extend the canonical input owner. The broader frozen replay exposed a linked consumer gap: Evidence’s existing blend-member purpose-tier rule did not recognize identity projections retaining the physical container path. Fix `6c8ac58b` extends that same Evidence owner using existing canonical parent lineage and linked lent-member provenance; no dose or primary floor is inherited. No new policy, field, registry, override or scoring owner is introduced.

The original two production regressions and the additional Evidence consumer regression failed before their fixes. Owner/consumer checks pass248+109+103; the strengthened Sensoril250mg dose assertion passes separately. The first completed-candidate whole-fast CI37426482664 failed on85672c8c:19,542passed/3failed/183declaredskips,with passing skip guards. Allthree failures reproduced in isolated nodes. Atomic e005a2dc fixes botanical recognition through the existing exact reviewed-material owner; c065d8a0 corrects obsolete pea/plant-part tests while retaining real source identity,lent blend mass,no primary floor,and cleaner-owned disclosure.36 affected tests and52 profile/route consumers pass. Final combined raw measurement at `c065d8a0` covers694 unique labels (660 prior sample,16 additional minus2 overlaps,and20 reviewed-brand cases):18 explained numerical movers. The660 captured outputs match the accepted6c8 source exactly;16 additional native artifacts differ only in scoring timestamps. Four Sytrinol,four TamaFlex andone Tesnor labels recover existing Formulation recognition; every label prints the actual curated material. All20 brand/control traces retain non-Formulation pillars,route,safety,Dose-safety,status,completeness andrecursive warnings. No registry or numerical policy changed. Fresh independent review accepts the complete candidate. Final combined checkpoint25adf10e is accepted: [whole-fast CI37428854698](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/37428854698) passes allfour groups with19,546checks and183declaredskips; every skip guard passes. Final local537passes/24declaredopt-ins in135.05s with passing skip guard. Candidate runtime/reference hashes exactly match independently measuredc065d8a0. Subsequent documentation-only changes reuse this source checkpoint. Sean authorized integration: PR68 merged as13b7a499, verified inorigin/main; its local/remote temporary branch is removed. The merged runtime equals the accepted candidate; automatic main CI may run again, but is not a new acceptance requirement for identical source. No artifact/release gate is marked complete. Pea protein uses the existing source-neutral Protein Supplementation record; [its primary meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC5867436/) includes a pea-protein condition. [NIH LactMed](https://www.ncbi.nlm.nih.gov/sites/books/NBK501771/pdf/Bookshelf_NBK501771.pdf) confirms silymarin contains silybin; overlapping constituent masses cannot establish complete blend disclosure.

Owner: `scripts/scoring_input_contract.py::_stamp_evidence_identity_contract/_derive_blend_header_anchor_from_nested_child/profile_owner_candidate_rows` and `scripts/evidence_resolver.py::_evidence_owner_selection/is_reviewed_branded_material` plus `scripts/scoring_v4/modules/botanical_profile.py::_recognized_botanical_identity` — evidence: `rg -n "scoring_input_contract|evidence_resolver|blend_anchor|reconcil|parent_source_path" scripts/contracts/source_of_truth_matrix.json scripts/GLOSSARY.md scripts/evidence_resolver.py scripts/scoring_input_contract.py`; corresponding Flutter stems and frozen raw/native-artifact probes. Will NOT create: another identity/role/scoring owner, persisted field/status, numerical policy, product override or publication approval.

October 6 current acceptance register — final070547: Sean completed the required post-PR68 run on main604e2b2c. All114 Clean/Enrich/Score manifests match current code/reference and content hashes;38datasets contain15,421rows per stage. The new candidate2026.10.06.131709 contains15,150products/blobs,271quarantines and zero export errors (core SHA438b1c8a3fa4ec08c1e65e70c704dfd67cfe64e9d040fadcc28917c52de604f4). All694 previously reviewed examples and132 clinical-warning captures match the accepted source. Catalog comparison retains all15,150IDs with no safety/status transitions;193 numerical movers still require the final shared-cause catalog review. Remaining release audits/full backstop and physical-device acceptance remain pending; publication and installation are unapproved. Master remains57/70; broader clinical coverage stays open.

The export snapshot gate found obsolete204571 total62.5 versus reviewed63.5; only its total and compatibility mirror changed. The existing raw snapshot freezer now provides a read-only complete-canary preflight, and the full batch runner stops before processing when it fails. This checks current production Clean/Enrich/Score owners rather than old stored outputs; it never auto-refreezes expectations.33 raw canaries pass,53 owner/consumer tests pass, and two fail-first regressions reproduce stale stored-output blindness and missing early abort. Missing/ambiguous/wrong-identity inputs fail explicitly. Validation class: test/infrastructure, with whole-fast CI37472652435 passes allfour groups on8ddb00dc:19,546checks/183declaredskips. No scorer/reference/public policy change and all stage fingerprints remain identical. PR70 is integrated as e4614f13 and its temporary branch is removed; every change goes through a PR before merge. Durable receipts: `/Users/seancheick/pg_quality/post_pipeline_20261006/final_run_070547/`.

Current check update: all15,150 catalog warning/allergen/safety/Dose-safety/completeness payloads match002121 exactly. App reader2passes covering every product; connected screens20passes. Paired bundle49passes/one known published-pin failure; unsigned iPhone build passes with allfour candidate asset SHAs exact and originals restored. Initial PR70 CI37471171010 completes:three groups pass,group1 fails five cases in one shared fake-repository dependency class. The existing batch test helper now installs a validated successful preflight stub so downstream orchestration assertions still run;53 owner/consumer tests pass,including allseven batch tests. No production guard is bypassed. Completed-candidate CI37472652435 is green on8ddb00dc:allfour groups/19,546checks/183declaredskips/skip guards pass. Source/tests are complete; subsequent documentation-only receipts reuse this checkpoint. CodeRabbit was rate-limited and did not review PR70. Release127tests pass; Evidence reachability recomputation covers all15,421 products with zero stale, newly reachable, unlinked or erroneous native matches. Release session completed successfully: 127 tests and all downstream/live gates passed; citation-content audit retains 252 baseline-triaged mismatches with zero new or unresolved findings. The subsequent full backstop was interrupted at approximately 93% with one visible failure and no final summary; it is not a completed checkpoint. Its historical last-failed cache does not identify the current failure. No new corpus pass.

Sean approved aggregate pipeline preparation on October 6. Bounded infrastructure batch codex/pipeline-preparation, baseline758fa4e6, PR72. Owner: scripts/preflight.py::run_preflight/run_preparation/_preparation_runtime; test_profiles.py/conftest.py/test.sh/test_lock.py; data_batch.INTENTIONAL_EXCEPTIONS; existing raw freezer and pipeline_freshness — evidence: definitions, matrix/glossary/stem/caller searches and fail-first production-seam probes. Will NOT create a second scorer, registry, public field/state, clinical policy, product override or approval owner.

Existing preflight now collects independent source/canary/live failures before full-batch processing, inventories every source/artifact/opt-in node, preserves strict complete evidence and source/runtime/input fingerprints, and retains post-run/export/publication gates. Named shell bookkeeping is excluded; meaningful configuration stays bound. Exact authored metadata exceptions come from the existing data_batch owner. Actual exclusive inherited locks, UTF8 protocol I/O, stable original calendar epoch and fresh final FDA verification are regression-covered. Every live command always reruns and has a 900-second wall deadline; timeout remains unresolved/failed, independent checks continue, and valid source receipts survive. No clinical or scoring source changed.

Distinct durable receipts under /Users/seancheick/pg_quality/pipeline_preparation_20261006/: ce0d6bf3 completed real preparation with all19checks passed,21,942source tests/16declared metadata skips/401deferred, stable inputs; unchanged-input reuse completed206.022seconds with fresh collection/live verifiers. The pinned launch proved identical-runtime reuse but exposed SHELL_PID as operational churn; a452bb67 fixes the existing runtime owner, with fail-first direct and real-shell controls. Its real aggregate completed21,944source tests/16declared metadata skips/401deferred and stable inputs, with22,361unique inventoried nodes (21,960source/372artifact/29external). RxNorm and medication-identifier commands were operator-stopped during provider slowdown; no identifier mismatch was established, and aggregate readiness stays false. Never restamp these receipts as current-source passes.

Final deadline source3d181d2a passes76focused owner checks and three real deadline/reuse/provenance controls. Sleeping live child is killed/reaped, independent successor completes, source receipts reuse, source mutation invalidates reuse, live success always reruns, and source checks retain no live deadline. Two fresh independent reviews accept exact3d181d2a. Infrastructure validation requires this bounded harness plus exact-candidate CI; the latency-only delta does not request another19-minute source run or corpus pass. Latest source plus documentation candidate a1aa0138 CI37512615303 passed allfour groups:19,603passed/183declaredskips/zero failures or errors; all skip guards passed (duplicate push37512608503 cancelled); no pending/cancelled run counts as green. Earlier exacta452 CI37506206590 passed allfour groups:19,601passed/183declaredskips/zero failures or errors.

All three existing stage fingerprints still match Sean's completed070547 pipeline; no corpus regeneration or publication performed. Master remains57/70. Current full live readiness,193catalog shared-cause movements, completed full backstop, physical-device/publication acceptance and broader clinical coverage remain open. Preserve main five tracked deletions, held app lane and unrelated worktree. Infrastructure qualification is complete. PR72 integration/containment and temporary cleanup are recorded in the current handoff after verification; next product acceptance is the shared-cause catalog review using existing outputs.

CodeRabbit outside-diff suggestion to defer UNII cache consumers was independently reproduced and rejected: scripts/api_audit/build_unii_cache.py imports the FDA bulk identity registry, not Clean/Enrich/Score output. The cache and canonical-name assertions are pre-run reference dependencies; absence/content already participates in receipt fingerprints. Moving these tests to artifact phase would hide a source blocker. Existing fast-profile categorization remains unchanged. Original UTF8/calendar review findings were reproduced and fixed.


### October 6 — individual Dose exposure repair (historical source checkpoint; current artifacts above)

The 193 catalog movements are reproduced and attributed through 225 frozen raw labels. That audit found preexisting blend totals being read as individual ingredient doses. PR73 corrects the shared exposure boundary while preserving existing whole-preparation12 and individual16 fallbacks, purpose averaging, typed EAA/BCAA aggregates and disclosed enzyme activity. No scoring magnitude, denominator rule, clinical target or public contract changes.

Owner: generic_helpers::has_usable_individual_dose, scoring_input_contract::is_lent_blend_mass/scoring_input_kind, generic_dose fallback and sports_dose::_score_primary — evidence: matrix/glossary/callers, raw fixtures and native census. Will NOT create: another scorer, registry, public field/state, clinical policy or product exception.

The independently reviewed final 2,615-product capture has 608 explained numerical movements and zero safety, Dose-safety, status, readiness, completeness or route changes. All 33 raw canaries pass; the five source-reviewed fixture refreshes regenerate identically. Local validation passes 537 checks / 24 declared optional skips. Exact candidate e7a02198 passes all four CI groups in run37524815261: 19,629 checks / 183 declared skips with green skip guards. PR73 is integrated at main8a7f2f6a; its automatic main CI37526236699 also passes.

The current-main preparation completes 18 of 19 checks, including every live verifier, final FDA freshness and unchanged inputs. The source suite reports 21,971 passes / one obsolete infrastructure score assertion / 16 declared metadata skips / 401 deferred cases. Tests-only4bdaee21 makes that drift test use deliberately stale ±1 output against the existing real production seam, preserving exact failure and no-write assertions; 49 named owner/consumer checks pass. The failed preparation receipt remains false. The next complete source checkpoint belongs to the existing automatic preparation before any brand in Sean's pipeline launch; no extra duplicate suite or receipt restamp is performed.

Master remains **57/70**. Actual fingerprints require the next run from **Clean**, with `--pipeline-only`; Sean runs it. New-artifact catalog/app parity, release/full backstops, device validation, publication approval and broader clinical coverage remain open. The iPhone is currently offline. No corpus run, publication or installation occurred. The execution [LEDGER](../../scripts/audits/pending_items_20260926/LEDGER.md) contains detailed receipts and remaining gates.


October7 continuation: fresh strict reachability and diagnostic stored census, original/live movement review, interaction byte parity and all-row Flutter/20host-screen checks now have current receipts in the existing LEDGER. Clinical source/role fixes form one bounded behavioral batch at73120c9e:44 verified factual records retain applicability limits, and source identity/role/disclosure corrections preserve honest form holds. Full15421-label raw baseline census corroborates278pending subjects; final2002+94 frozen-label comparison and262-product pending-cohort census are underway. All33 raw canaries pass after one reviewed readiness-only refresh. Combined movement review, independent review/CI/local/integration and refreshed final artifact validation remain open. Phone attempts did not complete physical acceptance, and app bundle/publication checks retain the genuine unpublished-pin/dependency failures. Sean confirmed sole use until beta ready and approved local device testing only. Counts remain57/70; see LEDGER October7 for evidence and exact limitations.

October7 bounded creatine correction: independent review reproduced borrowed monohydrate clinical credit for printed hydrochloride/ethyl ester; existing clinical applicability scope now requires the source preparation and preserves verified existing Creatin Monohydrate/Creapure aliases.158named owner/consumer checks and all33RAWcanaries pass at89df71c0. Final2249RAW/453native measurements are pending, followed by exact CI/local and authorized PR integration. Master57/70 remains unchanged; implemented/targeted-tested does not close release coverage. Sean reconfirms sole use until beta ready; publication still requires exact-candidate approval. See existing LEDGER for receipts and limitations.

Final89df71c0bounded review completed:2249RAWlabels/75explained numeric movements/4identityholds;453native traces preserve protected safety and lose no alerts;519subjectcensus haszero pending literature, with onlytwo honest bile identity holds307560. PR78 is open and whole-fastCI/local acceptance is pending. These measurements close the bounded source review, not the composite full-artifact clinical, app or release deliverables. Master57/70 unchanged.

PR78checkpoint: local537passes/24declaredopt-ins andpassingguard; firstwhole-fastCI19732passes/oneobsolete synthetic preparation pin/183declaredskips,allguards pass. Exact failure correctedtests-only62d867fbwith161focusedchecks; finalcombinedCIretry pending. Runtime/reference source stays identical to89dfmeasuredcandidate; no extra regeneration for this fixture correction. Master57/70 unchanged.

PR78automatedreview: two reproduced existing-owner corrections integrated locally—display score participation excludes existing non-efficacy roles while retaining assessed blend children, and known conflicting complete-form names cannot be overridden by a group. UnknownPoliSure remains honestlyheld.198targetedchecks andfreshsource reviewpass; generic cleaner-eligibility display guard was rejected by actual2219 native measurements and narrowed to the existing role owner. Finalsame-scope measurements andnewCI/local pending at43f2a5e9. Twootherbotrecommendations refuted againstactualowners (terminalannatto-sourceveto; qualitytierPoorversusretiredverdictPOOR). Onefinalnecessarycorpusrun remainsafterallknownfixes integrate. Master57/70 unchanged.

October7 before-run stop: all18other aggregate checks pass; source suite22,083passes/one obsolete bare-alginic-acid alias expectation/16declaredskips. Existing acid-versus-sodium-salt ownership remains correct. Tests-only expectation correction and negative/positive controls pass69focused checks in4.19seconds; Sean requested no repeated broad suite. Failedaggregate receipt remains preserved and failed; no corpus started or readiness restamp. Master57/70 unchanged. See LEDGER for the exactnode and launcher limitation.


### October 7 active canonical mapping completion

Sean requires the full held/unmapped set audited and resolvable mapping debt repaired through canonical owners before catalog-policy reconsideration. Completed October7 corpus/catalog remains comparison evidence. Source027447ee is committed on the temporary canonical-mapping branch, not integrated. Existing LEDGER/research and R7 receipts record all270held products/236unmapped rows/116groups, verified identities, assessment/manufacturer gaps and fail-first fixes. Catalog eligibility unchanged; no invented grade or per-product exception.

Shared root repairs cover exact preparations/species/source context, constituent-UNII versus whole extract, marker-proximate percentages and one declared-enzyme-activity parser across Clean/Enrich/scoring. Per-mass enzyme potency and canonical research notes cannot invent serving activity. Exact24IQM/5botanical/1clinical-entry checks pass, with no existing numerical IQM grade changed. Stable eight-file owner/consumer592checks pass; all33existingRAWcanaries pass unchanged.

Broader scope uses all15421manifest-owned products and15414brandRAW+9manual labels. All702enzyme products retained as controls; alias name/group census adds34products to1474frozen inputs, total1508comparison labels in two disjoint manifests. Earlier input hashes verified; superseded subset removed. Clean committed baseline/candidate RAW replay, protected-field cause review, fresh-context review, exact-source CI/local, PR/merge/cleanup and integrated final candidate validation remain pending. No new completion box is checked from focused tests. Genuine identity/manufacturer/assessment prerequisites remain explicit, and publication needs Sean's approval of the exact final validated candidate.


October7 broader-impact checkpoint: the1508RAW comparison reproduced six explicit-FCC-lactase holds and lost preparation/species safety precautions. Shared parser and existing clinical registry corrections are under targeted validation; all15421product safety-subject census adds406disjoint RAW controls (1914final replay). Primary-source warning review removes unsupported bark/salicin and liver safe-dose comparisons. No per-product exceptions, invented grade or new registry; no completion checkbox changes until final measurement/review/integration. Existing catalog remains baseline only. Exact results and initial failed checks remain in LEDGER and R7 receipts.


Independent1914impact review caught a shared enzyme-source regression despite zero automated-unattributed numerical changes: culture species could replace a discrete enzyme with a generic digestive-enzyme subject. Corrected at the cleaner source-form selector with six fail-first cases;271owner/artifact checks pass and33RAWcanaries remain unchanged. FullRAWsource-class census229rows/137products directs bounded current-source recapture; no product exception or whole replay/corpus repeated. This is still an active, unintegrated batch; previous1914capture is diagnostic, no new master checkbox or release approval.

October7 final bounded review accepted on fa82c7b3: independent reviewer verified all37 corrective identity changes and17 evidence projections, unchanged physical/activity quantities and zero interaction-profile changes. Independent census matched229rows/137products;16 independent focused checks pass. Complete137 current-source captures/hash checks pass. Composed1914 comparison (137fa82 affected-class captures +1777a8 controls where changed RAW predicate is absent) shows87numeric movers/36material,98not_scored→scored and zero reverse holds or automatically unattributed material movements. This is explicitly bounded mixed-source evidence, not a fresh1914fa82capture or integrated15421-product validation. Review: /Users/seancheick/pg_quality/post_pipeline_20261007/canonical_mapping_final_independent_review.md; comparison: canonical_mapping_composed_score_compare.json. No outstanding reproduced review finding. Exact-candidate CI/local, integration, final corpus/catalog/release/app/phone checks remain pending; master count62/70 unchanged.

October7 combined CI checkpoint9257621d run37695428205: FAILED, all four shards complete (10failed/19826passed/183skipped). All10failures classified:2copylength,2actual calcium unknown-share regressions,6stale expectations. Source0f6 shortens7notes without changing structured clinical content and grounds Dose fixture in actual declared activity;216owner tests pass. Tests-only stale preparation/floor expectations corrected against primary evidence,637checks pass. f7eea8a1 fixes shared unknown chemical-share shortcut while retaining original calcium17118 grade5.3 assertions;909owner checks/33RAWcanaries/19independent controls pass. Full15423RAW census539parent-local rows369products, verified using effective production parent inference with identical cohort.369before0f6/afterf7 captures:213IQD/1profile changes,125numeric2material/0status changes. Reviewer then found shared from-prefix association defect; cfaa9c49 preserves independent same-nutrient mineral/vitamin forms.5fail-first/914owner-consumer/25independent checks pass.52RAW replay22IQD/20profiles,15numeric9material/3scored→held; identities/amounts/activities/roles and warning decisions retained, calcium269360 twoform mean4.0, independent correction accepted.

Exposed3preparation gaps resolved in00e6a128 through existing calcium hydroxyapatite and generic iron amino-acid chelate aliases (NIHlabel correction/DoctorBestmanufacturer/Biotronsupplier; exactliveGSRS existing hydroxyapatiteUNIIverified). No grades/clinicalstrings changed. Exact2IQMentries/0problems;3fail-first regressions→22formshare checks,99owner/schema checks pass. Full15423RAW pattern census5products, only2additional smalllabels frozen.5sourceverified beforecfaa/after00e6 captures:3IQD/2profile changes,3held→scored,0pairednumeric changes;242994/334893 unchanged. Existing compound-duplicate owner retains1363mgwholepreparation separately from elementalCalcium300mg in269538/334893, before/after flags verified. Final same-reviewer source/bounded impact acceptance through00e6a128: no outstanding reproduced findings;27compound/Evidence consumer tests pass. Combined local78e8d5b2:537pass/24declaredoptional skips in150.23s, skipguardgreen. Whole-fastCI37700348887 on exact78e8d5b2: all4shards SUCCESS; required combined checkpoint accepted. All1475existing form grades unchanged,2178unique frozen RAW hashes verified across overlapping root-cause cohorts. Integrated PR83/origin6186cae9; primary640ce42e preservesprivate702efe41/userdeletions, production/rules/contracts match validatedorigin. All25intendedIQM entries exact-check0problems. Temporary ownedlinks removed, both managedworktrees archived and local/remote branch deleted. Integrated38Clean+38Enrich+38Score fingerprints stale; Sean will execute the necessary pipeline run. Agent preparation launch191917 was stopped at Sean’s instruction before any brand processing; exec54293 exited143, no corpus completion claimed. Durable stop receipt canonical_mapping_agent_launch_stopped.json; interrupted preparation remains not ready. Source batch is integrated/reviewed/CI-local validated, fingerprints require Clean. Await Sean’s pipeline completion, then verify outputs, build final candidate and continue app/release checks. Prior925local remains historical. Historical1914composed87numeric/98held→scored predates these source corrections and is not a final-source global claim. Final integrated fingerprints require one necessary Clean corpus, new catalog and release/app/phone checks. Publication remains unapproved. Redundant658146637-byte pre-fix derivedcomparison removed with checksum/compactreceipt and lossless native captures retained.

October7 preparation improvement checkpoint: interrupted human run preserved as failed/incomplete; no brands started. Existing owners now provide immediate check/elapsed/test progress and failure names, sealed exact-input partial-success reuse, one inventory/execution pass and memory-bounded two-worker evidence aggregation.656targeted checks and a53test actual parallel harness pass; harness selection is explicitly not full-corpus/source qualification. Corrected two stale identity expectations tests-only. Exact-source whole-fast CI37713894752 on2a672592 is SUCCESS across all4shards; final64owner/harness/ratchet checks and57actual parallel controls pass. Required infrastructure checkpoint accepted and PR84 integrated at origin1f750304/primaryedf07207 (private702efe41 and user deletions preserved); no clinical/release phase boxes newly closed. Sean owns the next necessary Clean→Enrich→Score run. Final candidate/catalog/app/phone/release checks and exact-candidate publication approval remain open. See execution LEDGER for evidence and limitations.


October7 preparation correction: latest human run failed source_tests before brands while all other checks passed. Shared mixed-phase parallel collection index defect reproduced and corrected; synthetic GALU fixture corrected to declared label activity, with notes-only negative control. Seven synthetic probes now belong to existing early/fast source tests; stored-product checks remain post-generation artifact checks.180focused owner checks pass; final52preparation/harness/ratchet checks pass. Exact-source whole-fast CI37717171034 on8cb85ece is SUCCESS/all4shards; PR85 integrated at origin6ac1c9af/primary5de76265; temporary branch/worktree removed. Master completion count remains62/70; Sean's corpus execution and final candidate validation remain open.


October8 human corpus completed:114 current manifests/174 owned files,15421 rows perstage, zero freshness issues. Preparation22,200 passes/16 declared skips reused; mainCI37718267849 SUCCESS. Fresh corpus corroborates all2178 reviewed mapping products with zero missing or differing public results; strict evidence reachability clean across15421 products. Current interaction database has132 verified interactions and152 canonical profile rules, exact source parity. Receipts: `/Users/seancheick/pg_quality/post_pipeline_20261008`. Final clinical census, gated catalog, original-baseline warning/movement comparison, Flutter/physical phone and release checks continue. Master62/70 unchanged; publication remains subject to Sean approval of the exact validated candidate.


October 8 current checkpoint: the fresh census exposed seven material-specific literature gaps (26 subjects/products) and a shared generic nettle/root scope conflict (110 subjects / 109 products). The canonical literature batch 2aad61f8 closes those reviewed determinations without clinical credit or dose benchmarks. Verified replay covers 136 products: zero numerical, status, route or other-pillar changes; 26 Evidence review-state/explanation changes. Independent review accepts the batch. Final local: 537 passed / 24 declared optional skips; 218 owner checks and all 33 raw canaries pass. PR 86 awaits integration; CI 37728838522 is SUCCESS. The changed reference content invalidates 114 stage stamps, including Clean; no manifests are restamped and no agent corpus is launched.

The successful 15,244-product catalog is now diagnostic for the updated Evidence copy. The app's production reader and 20 connected screens pass; full make check has 3,754 passes and one unpublished interaction-pin prerequisite. The signed iPhone build compiles, but physical validation is blocked by the locked Mac / undiscovered Dart VM (zero tests completed). Original app assets are restored. The original/live comparison has 38 unsigned exceptions: 25 milder summaries and 13 warning-bearing holds. Policy and exact publication approval remain open. Verified duplicate cleanup saves 2.508 GB plus 38.47 MB while retaining the current candidate. Receipts: /Users/seancheick/pg_quality/post_pipeline_20261008. Master remains 62/70.

The final bounded current-source census covers 136 raw products / 4,055 subjects with zero pending literature determinations. All 110 nettle subjects retain unestablished preparation applicability and zero points; only the two original bile-material unknowns on 307560 remain unresolved. Full regenerated candidate provenance and release/phone acceptance remain open.

October 8 exact-source acceptance update: whole-fast CI 37728838522 completed SUCCESS on 2aad61f8, all four shards and skip guards green. The final local and bounded raw/source receipts above remain applicable. The whole previous-candidate comparison covers 15,146 shared products / 98 added / zero removed; 69 numerical movers include 12 outside the original mapping cohort, now being classified by shared raw-label cause. An apparent seven-product warning-loss finding was disproved by direct artifact inspection and the production identity owner: all existing ginseng and nettle warning targets remain. Changed canonical identifiers were incorrectly grouped as removed-plus-added warnings; no redundant interaction rule or identity patch is justified. Receipt safety_identity_warning_retention_correction.json preserves actual field differences, including a multi-row ginseng dose-target selection for further review. Final candidate movement/release acceptance remains open.

October 8 final movement review accepted: all 12 outside-cohort numerical movers trace to Panax root, nettle root or unspecified black-cohosh preparation corrections. Independent full warning multisets clear all seven apparent warning losses; 218883 retains both powder and extract anticoagulant cards at their original evaluated amounts/severities. The grouping probe overwrote same-target rows; no production/data patch was made. Reviewed clinical runtime remains 2aad61f8, exact-source CI SUCCESS and local/canary/native measurement accepted. Final candidate regeneration, phone validation and publication acceptance remain open.

PR 86 MERGED at origin c666ac07100921bc105f6361fb9d40963bc410af; primary main a7ad49d90d89fefc1a5e0efd629ed85daa3ca94b preserves private702efe41 and all five user deletions. Final c10ebcc2 is contained in origin/main; only master/LEDGER documentation differs from tested runtime2aad61f8. Primary executable source matches origin exactly. Both previously modified primary documents were byte-verified included before integration. No primary main push. Owned worktree archived/removed, five generated-output/reference links removed without touching targets, local/remote clinical batch branches deleted. Superseded documentation-only CI37730573917/37730570738 cancellation requested; neither is acceptance evidence. Accepted exact-runtime CI37728838522 remains SUCCESS; automatic main CI37730576932 is pending and does not require another identical-source checkpoint.
Integrated freshness:38 Clean +38 Enrich +38 Score reference-content mismatches, no forged stamps. Seven material determinations and the nettle sibling are now on main; no remaining reproduced output-changing finding in this bounded batch. Sean owns the next necessary Clean→Enrich→Score pipeline-only refresh, after which reuse its outputs for final catalog/census/movement/app/release checks. The previous completed corpus and diagnostic candidate remain retained comparison evidence. Physical-device validation is blocked by the locked Mac/iPhone; zero device cases accepted. Exact-candidate publication approval is still absent. Master62/70 unchanged. Evidence: clinical_integrated_stage_freshness.json, clinical_final_ci.json, clinical_primary_document_preservation.json, clinical_worktree_link_cleanup.json, warning_identity_independent_multiset_review.json.

### October 8 final validation checkpoint — source unchanged
The 401-node deferred backstop finished with 371 passes, 29 optional live-stack skips and one stale generic-module canary expectation (328825). Its actual label exposure is 2,000 mg/day against the existing 500–1,000 mg preparation window. The tests-only repair pins 62.5 plus formulation/dose/evidence/transparency attribution and exact exposure/band; all three generic canary cases pass. No scorer, clinical data or output changed; the failed historical run is not relabeled green. The five direct live RxNorm/UMLS verification tests were explicitly enabled and all passed. Together with the retained source receipt, coverage is 22,587 passes and 40 declared skips across 22,627 nodes, subject to final receipt/fingerprint reconciliation.
App PR94 (https://github.com/seancheick/Pharmaguide.ai/pull/94) corrects the PR93 fixture assumption: all nine fixtures read authored severity from the active database and independently assert consumer parity. Both checksum-verified published and candidate artifacts pass three canaries each; 81 severity/Quick Check/database controls pass. Integrated app SHA 3847e0a3424388dc6d602dfd94867b9fe12cdd34; CI 37747691308 remains pending. Original dirty app assets are preserved.
Owner: scripts/tests/test_v4_cross_module_canary_diversity.py::test_generic_real_catalog_canary_score_and_traits; app test/release_gate/quick_check_catalog_interaction_test.dart — evidence: final_generic_canary_repair.log, curcumin_canary_label_daily_exposure.json, app_canary_artifact_parity_result.json and app_severity_owner_tests.log. Will NOT create: new score policy, form grade, source registry or product exception. Validation class: tests only, with production unchanged. Release rung is running against the exact frozen candidate; actual simulator launch still requires Rosetta and the 13 warning-bearing catalog holds require Sean’s catalog-policy decision. Publication remains blocked, not authorized away.
