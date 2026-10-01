# PharmaGuide master completion plan

Updated October 1, 2026. Pipeline integrator: Codex. Original scope: Sean's accepted September 30 master plan. This document is the readable checklist; [LEDGER.md](../../scripts/audits/pending_items_20260926/LEDGER.md) remains the execution register, and the [ownership matrix](../../scripts/contracts/source_of_truth_matrix.json) defines production owners. Historical descriptions below do not override current code or approved decisions.

A checked implementation box means that specific deliverable is implemented, measured and independently reviewed where required. It does **not** mean the whole phase is finished or the catalog is released. Repository code pushed to GitHub and catalog publication are separate events.

## Current checkpoint

- [x] Reconcile current main and the integration lane, including the release/storage changes on `d021061b`.
- [x] Integrate and push the approved probiotic production model and Ravage correction to pipeline `main` (`0f695b19`; Q47/Q48); source and plan subsequently pushed through `3ee91eae`.
- [x] Match the approved probiotic candidate across 1,259 frozen labels: 542 probiotics and 717 controls; no numerical/component/tier/route/status/Safety/confidence mismatch.
- [x] Close Ravage's cinnamon expected failure with a cleaner-owned fix, not a scorer exception.
- [x] Complete the latest source checkpoint: **17,915 passed, 167 skipped, zero expected failures** at `3ee91eae`, with independent review. Artifact-dependent skips still require release-stage checks.
- [ ] Complete the remaining Phase 2 role/prominence and serving corrections.
- [ ] Validate a fresh complete catalog, approve its exact manifest, publish and verify live behavior.

No catalog release has occurred under this plan. The latest checkpoint validates source and frozen samples, not the entire rebuilt corpus.

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
- [ ] Recheck SHAs, surviving worktrees, inputs and artifact freshness at the final candidate freeze; this is a recurring requirement, not a one-time guarantee.

### Phase 1 — Evidence → Dose separation

- [x] Produce the all-route ownership inventory and measured transfer packet ([packet](../../scripts/audits/evidence_dose_transfer_20260930/README.md)).
- [x] Approve probiotic certainty **0–10**, applicability **0–6**, independent same-condition replication **0/2/4**. An applicable material conflict suppresses replication only. No companion Evidence or category ceiling.
- [x] Migrate probiotics through existing owners; retain CFU/trial-amount assessment in Dose, preserve clinical guards and remove the experimental/retired 12+8 path.
- [x] Prove exact approved-candidate numerical equivalence, migrate tests semantically, pass the full fast suite and obtain fresh review (Q47).
- [ ] Transfer remaining generic clinical-amount judgments only after the existing Dose owner consumes their applicable benchmarks.
- [ ] Settle and integrate omega purpose/applicability mapping; carrier oil mass supplies neither EPA/DHA exposure nor clinical credit. The blanket O1 proposal remains rejected (Q45).
- [ ] Recheck every removed amount gate against the transfer inventory: no lost assessment and no duplicate deduction.

**Invariant:** an amount judgment cannot leave Evidence until the same judgment is already in Dose or is added to the existing Dose owner in the same change. Removing amount gates must not automatically award full Evidence marks.

### Phase 2 — Identity, roles and prominence — current lane

- [x] Preserve landed Lane 2A subject ownership, Q3 single sugar/sweetener charging and Q40 cleaner-owned plant part.
- [x] Fix Ravage cinnamon at the cleaner's functional attribution seam; retain explicit flavors, active/other membership, source paths and undisclosed member dose (Q48).
- [x] Measure Ravage and five controls, then the extended 1,259-label cohort; obtain fresh review and **zero expected failures** in the full fast checkpoint.
- [x] Correct trace-protein purpose for EAA product `66953` through shared roles and sports Evidence/Formulation/Dose consumers (Q39(b), source `3ee91eae`, pushed). Final fast suite passed; fresh review accepted clean replays. Total 49.1→37.0 is explained, Safety unchanged; five targeted and all 1,259 extended controls retain identical full payloads. EAA research remains open in Phase3.
- [ ] Replace `_primary_mass_floor`'s private primary selection with shared role facts; inspect the related generic recovery/collagen prominence consumers together. Preserve identity, source-lineage, structural and deduplication guards.
- [ ] Resolve remaining alternate-serving identity/duplicate cases from raw JSON (Q39); never merge materially different preparations or discard label variants.
- [ ] Align dual-use active/excipient decisions without using amount as a substitute for purpose. Preserve genuine excipients and nutrition rollups.
- [ ] Recompute the final Evidence-subject census after these corrections and classify all holds and changes.

Do not introduce the rejected mass-based demotion of purpose ingredients. Keep source-section membership separate from efficacy ownership.

### Phase 3 — Evidence research

- [x] Complete the registry-state inventory and repair the obsolete determination token without weakening specific identity/applicability holds (Q43; [receipt](../../scripts/audits/evidence_completion_20260930/README.md)).
- [x] Preserve verified probiotic preparation/population/purpose, primary outcomes, review approval and trial-family independence in production migration.
- [ ] Audit coverage against the **corrected release subject set**, not just the earlier registry census.
- [ ] Finish omega preparation/purpose applicability and the remaining generic/branded-formula coverage, including Tesnor/Sytrinol.
- [ ] Verify each remaining identity, preparation, intervention, population, outcome and identifier against live primary sources; document negative searches.
- [ ] Ensure no release-eligible subject has a pending Evidence determination; insufficient identity remains a justified hold.

A completed determination may be applicable positive evidence, reviewed null/no effect, inapplicable or combination-only evidence, or a bounded no-qualifying-human-evidence review. It does not mean every ingredient gets positive points.

### Phase 4 — Dose policy packets — decisions still required

- [x] Preserve accepted rules: known amount/applicable benchmark receives proportionate treatment; undisclosed amount has its correct zero reason; missing benchmark is not zero dose; BCAA/EAA sets are assessed once.
- [ ] Produce missing-benchmark cases for one through four purpose ingredients: wiring miss, unsupported benchmark, preparation mismatch, missing amount and incidental unbenchmarked ingredient.
- [ ] Show per-ingredient assessment, denominator, pillars, total, tier and publication behavior, including current `not_scored` consequences.
- [ ] Produce the excess packet separating appropriateness from Safety risk, with exposure basis, form, population, duration and UL basis.
- [ ] Obtain Sean's approval for magnitudes, denominator treatment, explanations and publication behavior before implementation.
- [ ] Implement only the approved decisions in existing owners and measure their effects.

### Phase 5 — Numerical calibration and overlap

- [x] Produce the initial six-pillar numerical-ownership inventory ([inventory](../../scripts/audits/numerical_ownership_20260930/README.md)). Inventory is not calibration approval.
- [ ] Finalize `fact → judgment → pillar → production symbol/config key → other observing pillars` for every live numerical rule.
- [ ] Inspect all 35 Q3 legacy `POOR → SAFE` crossings individually, preserving the distinction between quality threshold and safety concern. Inspect subsequent safer Safety-verdict changes equivalently.
- [ ] Resolve remaining duplicate deductions, floors/caps, certification/disclosure overlap and fiber detox/laxative overlap.
- [ ] Ratify the reviewer brief, freeze the new benchmark and obtain independent review/approval for final magnitudes.
- [ ] Explain every score/tier/verdict movement. Seed and the BB12 anchors are canaries, not target scores.

### Phase 6 — Flutter parity and nutrition

- [x] Implement and review the separate Flutter lane's taxonomy, numeric/zero daily-value rendering and seven diagnosed golden updates (`2de825fe`, `e21df0fd`, `d5de1023`, `ec7b1530`). Its recorded app gates passed; this is lane validation, not frozen-candidate acceptance.
- [x] Fix the pipeline's daily-value loss at the cleaner owner and verify real-product `214452` rendering with a local candidate.
- [ ] Integrate the Flutter lane against the final pipeline candidate; recheck all condition IDs, contract parity, app tests and analysis.
- [ ] Verify nutrition/active/other sections, full label-row rendering and summary fallback: amounts, exact units, available daily values, explicit zeros and absent values.
- [ ] Confirm no app calculation recreates a pipeline score, verdict, role or Evidence determination.

### Phase 7 — Candidate, approval, release and live verification

- [ ] After the last source/data change, run one fresh corpus from **Clean**, publication disabled; no competing full suite.
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
