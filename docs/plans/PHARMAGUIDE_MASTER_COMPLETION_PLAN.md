# PharmaGuide master completion plan

Updated October 4, 2026. Pipeline integrator: Codex. Original scope: Sean's accepted September 30 master plan. This document is the readable checklist; [LEDGER.md](../../scripts/audits/pending_items_20260926/LEDGER.md) remains the execution register, and the [ownership matrix](../../scripts/contracts/source_of_truth_matrix.json) defines production owners. Historical descriptions below do not override current code or approved decisions.

A checked implementation box means that specific deliverable is implemented, measured and independently reviewed where required. It does **not** mean the whole phase is finished or the catalog is released. Repository code pushed to GitHub and catalog publication are separate events.

## Completion measure — October 4

**Main Phase 0–7 checklist: 50 of 68 boxes complete (73.5%, rounded to 74%).** Count only the eight phase sections under Updated execution checklist, including their nested deliverables; exclude historical checkpoint sections and repeated release reminders. This is an unweighted deliverable count, not an estimate of elapsed time, effort or release readiness. All document checkboxes would give222/263 (84.4%) before this update, but repeated historical receipts make that unsuitable as the main progress measure.

| Phase | Complete / total |
|---|---:|
| 0 — Baseline and final freeze | 3 / 4 |
| 1 — Evidence/Dose separation | 9 / 9 |
| 2 — Identity and roles | 15 / 17 |
| 3 — Clinical Evidence coverage | 6 / 11 |
| 4 — Approved Dose policy | 6 / 6 |
| 5 — Numerical calibration | 6 / 6 |
| 6 — Flutter parity and nutrition | 3 / 6 |
| 7 — Candidate, approval and release | 2 / 9 |

Approved scoring policy, implementation and bounded numerical calibration are complete. Broader source-section/role and clinical-determination coverage, current-source candidate validation, actual-device rendering, movement approval, publication and live verification remain open. Historical corpus/release passes do not validate the subsequently changed runtime. The execution LEDGER and main-checkout handoff carry the next steps; automation is deleted and jobs remain stopped pending the next authorized task.

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

**Next clinical-review sequence — no rank-fitting or numerical tuning:**

1. [ ] PHGG/Sunfiber: exact preparation and population/outcome applicability, clinical certainty/replication and why the current raw18/reference18 becomes Evidence20/20. Studied amount matching is assessed by existing Dose, not charged again in Evidence.
2. [ ] Inulin/FOS: exact preparation/source mapping and applicability for Nutricost, Jarrow and BulkSupplements; audit the current15.6 Evidence credit against verified interventions and endpoints.
3. [ ] XOS/PreticX: preparation versus active-equivalent identity, generic versus branded evidence, clinically meaningful versus microbiome endpoints and existing Dose benchmark wiring.
4. [ ] GOS: inspect GNC's low-end comparator and its actual preparation/intervention; unresolved research is not proof of no efficacy.
5. [ ] PreforPro/bacteriophage: exact marketed intervention, standalone versus combination attribution, patient outcomes versus microbiome endpoints and studied-dose applicability.
6. [ ] Probiotic strain/formula families: exact strains versus species records, blend/formula applicability, population/outcomes, replication/independent confirmation and sponsorship provenance. Total CFU never becomes a per-strain dose. Include Seed and the currently credited IS-2/LactoSpore families.

Then compare certainty/applicability principles across PHGG20, inulin15.6, Seed14.5, PureXOS0 and Thornephage0 before approved Dose policy/calibration changes. Review funding descriptively under existing policy; do not invent sponsorship deductions. Keep Nutricost87.1 and all Q59 scores as the frozen baseline until a verified clinical finding or approved policy justifies a change.

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

## How to read the remaining Phase 0–2 boxes

The October 1 source audit reconciled these boxes against current production and the existing receipts. An unchecked box means a real outstanding deliverable or an explicitly named later gate; it is not permission to skip it.

| Item | Current status | What happens next |
|---|---|---|
| Phase 0 final baseline/artifact recheck | Current source reconciliation complete; final gate pending | Repeat at the exact candidate freeze, after the last scoring/data change |
| Phase 1 generic amount transfer / D26 | Implemented, measured and independently reviewed | Validate on Sean's fresh full corpus before release |
| Phase 1 omega Evidence mapping | Implemented with applicability holds | Validate all eight classes on the fresh full corpus |
| Phase 1 transfer-invariant audit | Closed for current source | Recheck rebuilt artifacts at release gate |
| Phase 2 shared prominence owner | Implemented, measured, reviewed and integrated | Marked complete; retained amount guards stay under Phase 1/D26 |
| Phase 2 remaining serving duplicates | Closed for current raw corpus | Recheck canonical output and app rendering after fresh Clean |
| Phase 2 dual-use ingredient roles | Ravage/trace-protein examples corrected; broader class open | Inspect current source/purpose facts and correct shared owners without amount-based demotion |
| Phase 2 final subject census | Pending corrected subjects | Recompute after the remaining source corrections; classify holds and deltas |

**Work can proceed now without a full corpus job:** prepare the Phase 1 benchmark/policy packets and fix the remaining Phase 2 source classes with focused tests and bounded raw replays. The final census and candidate gates follow those changes. Sean runs the full pipeline when the final source is ready; Codex reviews its artifacts afterward.

## Fixed boundaries and Owner Check

| Decision | Existing production owner | Evidence |
|---|---|---|
| Shared purpose/prominence roles | `scripts/scoring_input_contract.py::classify_ingredient_roles` | Current consumers and role tests; correctness still needs Phase 2 work |
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
- [ ] **FINAL-CANDIDATE GATE:** Recheck SHAs, surviving worktrees, inputs and artifact freshness at the final candidate freeze. Current source/branch reconciliation is complete; this later recheck stays open until the release candidate exists.

### Phase 1 — Evidence → Dose separation

- [x] Produce the all-route ownership inventory and measured transfer packet ([packet](../../scripts/audits/evidence_dose_transfer_20260930/README.md)).
- [x] Approve probiotic certainty **0–10**, applicability **0–6**, independent same-condition replication **0/2/4**. An applicable material conflict suppresses replication only. No companion Evidence or category ceiling.
- [x] Migrate probiotics through existing owners; retain CFU/trial-amount assessment in Dose, preserve clinical guards and remove the experimental/retired 12+8 path.
- [x] Prove exact approved-candidate numerical equivalence, migrate tests semantically, pass the full fast suite and obtain fresh review (Q47).
- [x] Correct D26 collagen preparation/source binding through existing owners (`c8f53b46`);285 frozen controls identical,18,018 fast checks passed and fresh review accepted. This fixes source ownership, not the remaining amount transfer.
- [x] Verify all nine uncovered benchmark groups/four retained D26 stand-ins and prepare the whole D24 denominator/publication/excess and omega decision packet (October2 combined batch,86synthetic/16real probes).
- [x] Transfer remaining generic clinical-amount judgments after approval and equivalent existing-Dose ownership. Exact positive applicable preparation benchmarks only; the four D26 safeguards were removed only after Dose coverage existed.
- [x] Integrate omega purpose/applicability mapping; carrier oil mass supplies neither EPA/DHA exposure nor clinical credit. Ordinary adult / triglyceride-purpose / prenatal map to 10.4 / 20 / 11.1 and the five excluded classes remain held.
- [x] **PHASE-1 EXIT CHECK:** Recheck every removed amount gate against the transfer inventory: no lost assessment and no duplicate deduction. The 344-label replay has zero status, safety, route or purpose movement.

**Invariant:** an amount judgment cannot leave Evidence until the same judgment is already in Dose or is added to the existing Dose owner in the same change. Removing amount gates must not automatically award full Evidence marks.

### Phase 2 — Identity, roles and prominence — completed fixes and remaining source work

- [x] Preserve landed Lane 2A subject ownership, Q3 single sugar/sweetener charging and Q40 cleaner-owned plant part.
- [x] Close the bounded CFU source cases `242637` / `242654` / `327966`: statement exposure and guarantee use the selected panel serving; `327966` remains 50 B through expiration. Final 455-label replay explains all nine changed payloads and preserves 446 controls. Broader alternate-serving and role classes remain open.
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
- [ ] **SOURCE WORK NEXT:** Align remaining dual-use active/excipient decisions without using amount as a substitute for purpose. Ravage and trace-protein corrections are completed examples; the broader class remains open. Preserve genuine excipients, source-section membership and nutrition rollups.
- [ ] **AFTER SOURCE CORRECTIONS:** Recompute the final Evidence-subject census after the remaining serving/role corrections and classify all holds and changes. Earlier frozen cohort checks do not establish this final census.

Do not introduce the rejected mass-based demotion of purpose ingredients. Keep source-section membership separate from efficacy ownership.

### Phase 3 — Evidence research

- [x] Complete the registry-state inventory and repair the obsolete determination token without weakening specific identity/applicability holds (Q43; [receipt](../../scripts/audits/evidence_completion_20260930/README.md)).
- [x] Preserve verified probiotic preparation/population/purpose, primary outcomes, review approval and trial-family independence in production migration.
- [x] Independently identify source/strain attribution defects in the generic longum and acidophilus records (Q53); record a release hold rather than treating unchanged scores as clinical validation.
- [x] Correct Q53 through the existing registry/applicability owners: two per-entry source reviews, canonical reference-only veto, 536 frozen raw labels plus one preserved submission, and fresh independent review. All 54 DSLD score decreases are Evidence-only; existing native-strain assessments are unchanged.
- [x] Integrate Q53 final source checkpoint on main through `6a15be14`, including the corrected BB536 preservation canary; combined fast18,008passed/168skipped/zero failures or xfails.
- [ ] Validate broader Evidence coverage on the fresh release candidate. Eight labels now expose incomplete Evidence coverage; one already-incomplete label adds an unresolved subject. Research queue:12091,1834,19171,19172,19890,264105,35694,46802,65049 (`probiotic_q53_20261001/research_queue.json`). These are research/identity checks, not a reason to restore unsupported species credit.
- [ ] Audit coverage against the **corrected release subject set**, not just the earlier registry census. October 2 marine-attribution correction exposes ALA determinations that remain unreviewed; rejection of a marine record is not a completed negative ALA assessment. Recheck every release-eligible ALA subject; affected examples12315,18141,241665,293406,295103,295198,295470,328010,328011,840.
- [ ] Finish omega preparation/purpose applicability and the remaining generic/branded-formula coverage, including Tesnor/Sytrinol.
- [x] Verify the nine-label Q53 and eight-family indexed/bounded source batch together; document live identity/material/outcome checks and bounded negative searches in the existing research register (October2).
- [ ] Complete remaining clinical determinations, generic/branded source verification and broader release-eligible coverage; source review does not resolve insufficient identity or approve a new positive grade.
- [ ] Ensure no release-eligible subject has a pending Evidence determination; insufficient identity remains a justified hold.

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
- [ ] Confirm no app calculation recreates a pipeline score, verdict, role or Evidence determination.

### Phase 7 — Candidate, approval, release and live verification

- [x] Audit Sean's October 1–2 intermediate Clean/Enrich/Score run: 38 datasets, 15,421 scored artifacts, 114 matching input/code/content manifests; 46 accepted CFU/control products retain all public pillars, totals, tiers and typed safety. This is a completed checkpoint, not the final candidate: downstream snapshot guard exposed two source defects, corrected in the October 2 batch below.

- [x] After the last source/data change, run one fresh corpus from **Clean**, publication disabled and without a competing broad suite. Accepted run: `batch_run_summary_20261003_123945.txt`;38 stage chains/114 current manifests.
- [ ] Rebuild catalog, interaction output and canaries; run release gates and the full backstop sequentially.
- [ ] Freeze candidate SHAs, config/data fingerprints, catalog generation and artifact hashes.
- [ ] Produce counts/holds/statuses, route changes, newly scored/held items, largest 50 score deltas, all safer-verdict and BLOCKED changes.
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


### October 4 — bounded beta pre-run closure

- [x] Sean clarified publication policy: unresolved identity/form products remain withheld; confirmed banned/recalled products still ship BLOCKED with their reasons. A CAUTION warning alone does not exempt an unresolved product. No new public status or publication exception.
- [x] Fresh frozen-raw replay of 47 labels confirms all37 prior-caution form holds remain withheld. Bitter Orange/Citrus aurantium source exclusions are deliberate and regression-pinned; unresolved mixtures, chemical preparations and contradictory source forms are not forced matches. Per-product dispositions are retained in beta_prerun_closure_20261004/held_product_dispositions.json.
- [x] Inspect original catalog drivers for six milder cases:18529/5862/5864 had DOSE_OVER_UL_CRITICAL, including the confirmed Copper unit error;219819/219827/219832 had B0_HIGH_RISK_EXCIPIENT_WARNING_ONLY and a historical high-caffeine flag. Existing source/daily-exposure corrections and advisory-versus-verdict policy explain current outcomes; warnings remain independently represented. This batch changes none of these six scored/gate records.
- [x] Fix264105 exact LA-5 form lost under Advanced Acidophilus heading in the existing studied_formulas::clinical_strain_identity_from_label owner (58dd0ac9). Require agreeing source species, one fully printed identity, source lineage, no conflicting scientific name/code. Reuse existing designation parser; do not create another taxon parser. Independent review caught abbreviated conflicting species; final regression covers it.
- [x] Focused identity/collector/public-artifact slice131passed5optional corpus skips. Two frozen cohorts47+9:47 unchanged; only264105 moves44.8→59.9, Formulation2.7→13.3/Dose9.1→13.6 under existing identity/disclosure rules. Evidence0 stays0; route/status/safety unchanged. Eight clinical controls unchanged. No magnitude, registry grade, benchmark or safety policy changed.
- [x] Independent live source review: nine NIH source labels match retained rows/servings/statements. Remaining Q53 identities stay honestly unresolved; LA-5 gut Evidence remains zero. PHGG/inulin/XOS/GOS/phage grading/preparation questions remain later clinical-policy gates, not invented positive findings.
- [ ] Final measured review and exact candidate CI/local checkpoint, then integration to main.
- [ ] Sean runs one Clean→Enrich→Score corpus pass with --pipeline-only. Canonical fingerprint preflight found all38Clean manifests stale; an Enrich-only run is insufficient. No corpus run or publication started by this batch.

Owner: scripts/studied_formulas.py::clinical_strain_identity_from_label; scripts/probiotic_measurements.py::label_strain_identity_resolution/_label_designation_tokens; existing cleaner/enricher, scored artifact and build_final_db publication qualification. Evidence: source matrix/callers, fail-first wrapper regression, public scored-artifact regression, frozen47+9 raw-label replays and independent source review. Will NOT create: scorer, parser, registry, status/field, publication exception or numerical policy. Receipts: /Users/seancheick/pg_quality/beta_prerun_closure_20261004/.

Next after the new corpus: build and inspect the candidate catalog/interactions/app, align the existing movement gate with authorized cause-based development review (without forging approvals), run sequential release/full and real-device checks, freeze manifest and obtain external publication approval. These artifact/consumer checks do not require another corpus pass unless source or provenance actually changes. No whole phase is closed by this bounded batch.
