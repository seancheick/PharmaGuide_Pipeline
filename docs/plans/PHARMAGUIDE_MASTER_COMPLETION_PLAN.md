# PharmaGuide master completion plan

Updated October 1, 2026. Pipeline integrator: Codex. Original scope: Sean's accepted September 30 master plan. This document is the readable checklist; [LEDGER.md](../../scripts/audits/pending_items_20260926/LEDGER.md) remains the execution register, and the [ownership matrix](../../scripts/contracts/source_of_truth_matrix.json) defines production owners. Historical descriptions below do not override current code or approved decisions.

A checked implementation box means that specific deliverable is implemented, measured and independently reviewed where required. It does **not** mean the whole phase is finished or the catalog is released. Repository code pushed to GitHub and catalog publication are separate events.

## Current checkpoint

- [x] Reconcile current main and the integration lane, including the release/storage changes on `d021061b`.
- [x] Integrate and push the approved probiotic production model and Ravage correction to pipeline `main` (`0f695b19`; Q47/Q48); source and plan subsequently pushed through `3ee91eae`.
- [x] Match the approved probiotic candidate across 1,259 frozen labels: 542 probiotics and 717 controls; no numerical/component/tier/route/status/Safety/confidence mismatch.
- [x] Close Ravage's cinnamon expected failure with a cleaner-owned fix, not a scorer exception.
- [x] Complete the earlier integrated source checkpoint: **17,915 passed, 167 skipped, zero expected failures** at `3ee91eae`, with independent review. Artifact-dependent skips still require release-stage checks.
- [ ] Complete the remaining Phase 2 role/prominence and serving corrections.
- [ ] Validate a fresh complete catalog, approve its exact manifest, publish and verify live behavior.

No catalog release has occurred under this plan. Recorded checkpoints validate their named source and frozen samples, not the entire rebuilt corpus. Current main was fetched at `e8687b39`; the isolated Codex audit checkpoint is tracked separately in Phase 2.

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
  - **Audited, not integrated (October 1):** Codex pinned Claude production `b43a048f`, independently reproduced member-named blend headings borrowing member amounts, and committed corrections through `9f7837e8` on `codex/quality-completion`. Source facts use the existing scoring-input contract; branded-floor eligibility rejects a multi-member total containing the named branded member. The broader prototype was rejected after raw replay exposed whole-preparation regressions. The narrowed implementation preserves Mirtogenol, phytosome, Relora and standalone UC-II preparation controls.
  - [x] Independently reproduce the heading/member defect, implement failing-first owner fixes and obtain fresh review of the narrowed correction.
  - [x] Measure the narrowed fix against pinned `b43a048f`: 185/186 real labels identical; product `321351` loses a UC-II floor borrowed from its 10 g mixed-collagen total (70.4→54.8, Evidence 20→4.4, clinical points unchanged). Fifteen adversarial/control cases: eleven identical, four edited member-heading variants lose only the invalid Evidence floor. See the [audit receipt](../../scripts/audits/prominence_ownership_20261001/README.md#codex-independent-audit--october-1).
  - [x] Final full fast checkpoint at `b0c51483` (production unchanged from `c6ea928d`): **17,823 passed, 307 skipped, zero failures and zero expected failures**; exit zero. Skips include missing stored artifacts and Node-dependent console tests; these are not release validation. Focused protections: 53 passed. First complete run: 17,961 passed, 167 skipped, one stale probiotic archetype expectation failed. Its generic species credit was independently traced and the expectation corrected; all 41 archetype checks pass. Canonical-provenance canary independently passed after replacing its obsolete corpus fixture with a fresh production-boundary extraction.
  - [x] Complete the unit-selection correction packet: `c6ea928d` uses the existing converter so 10 g beats 300 mg, while exact source rows stay authoritative. Failing regression reproduced, 143 focused checks passed and fresh review accepted; all twelve frozen raw labels remain identical and all 186 controls retain identical captured payloads. No new Dose policy or benchmark.
  - [x] Reproduce and correct the symlinked manifest-path assertions (`b0c51483`); all three real-product clinical identity checks pass unchanged. The citation-parser timeout passes on focused rerun without data or timeout changes. The isolated combined checkpoint passed as recorded above.
  - [ ] Reconcile and independently validate Claude's later production `68cae99a` (including BCAA/collagen safeguards and recovery behavior for non-owner-scoped callers); latest fetched feature tip `002d2683`. Earlier pinned measurements do not validate later code.
  - [ ] Implementation and all-cohort measurement validated by Claude on one frozen final candidate.
  - [ ] Codex integration; Q49 remains open. No main merge, push or release in this audit.
  - [ ] Decision D26 and Evidence→Dose transfer: relative mass comparisons remain legacy eligibility gates, not reviewed clinical benchmarks. Latest Claude source retains four comparisons (primary floor, ingredient recovery, authority and collagen recovery). Do not silently transplant these heuristics into Dose. Bind any reviewed minimum to its actual matched preparation/source row before assigning amount ownership.
