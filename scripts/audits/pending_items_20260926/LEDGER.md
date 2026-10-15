

## Step3 closed; Step4 started — October15

Owner: `enhanced_normalizer.py::_extract_nutritional_info`, `enrich_supplements_v3.py::_collect_nutrition_summary`; scoring/quality/completion owners for the remaining batch. Evidence: matrix/GLOSSARY/stem search and STEP3_OPTIONS.md. Will NOT create: scorer, status/registry, runtime product-ID exemptions or restamped artifacts. Sean authorized the recommended option and starting Step4; main merge, rebuild and release held.

Step3: all70 remaining NIH label records reviewed (61 unique rendered pages), matched to their own component where a pack shares one image. All omit a sugar quantity. Conditional per-component bounds only; never exact0 or whole-pack inference.88 total PDF review receipts. Proposed incomplete221=155existing+66unfinished, down from293. Reviewed-bound/incidental class137. Full15123 comparison rerun: recommended mean+0.64,2637 provisional tier changes;0errors/untouched changes; all three options221partial. No numeric projection changed solely because the70 source reviews completed.

Missing-data validation expanded: fresh77 amount mutations+9 sports guards+23 new cases (18 identity,3 sugar-line,2 strain-to-total),109 unique cases; no higher eligible score or incomplete→complete upgrade. Retain fail-first receipts for173776/206322/69317. Source-aware private guards distinguish lost source declarations from newly verified manufacturer omissions; they are not production acceptance. Aggregate conversions preserve15billion total, remove5/10billion per-strain allocations, Dose13.3→0 and60.1→41.2; no "underdosed" inference. Existing9sports/382probiotic/82retained and transform-order guards rechecked;58enriched input hashes unchanged.

Step4 source + B7 slices: commits478a4e8d/27a60266/6d0b6321/1a161d9c/3a7b3143. Existing source owners retain sugar provenance and variants; three label-verified unit corrections preserve0g/<1g/1g+3g. Delivery requires a physical capsule/tablet/coating/shell claim, not acid-resistant strains. B7 is charged in Dose once; remove the dead mirror helper/group/config, receipt and contradictory copy. Owner matrix updated. Tests:106delivery,32replay,79nutrition,104correction,249B7 owner/consumer cases passed (overlapping slices, not a unique-test total). Three correction cases and three B7 ownership cases failed first. Exact data batch:3changes/0problems.

Canonical raw + artifact checks13labels against clean7ae56ad0a:25987964→60 unsupported delivery removed;24228454.8→56.8 duplicate B7 removed, Dose unchanged. Other11 totals unchanged;13/13 assessment,score-status and safety outcomes unchanged. Legitimate capsule controls retain credit; original sugar qualifier/columns retained. Evidence private step4_source/dose replay manifests, snapshots/deltas and step4_artifact_* receipts. Behavioral scoring/source class. Local rung on runtime3a7b3143:532passed,38skipped,exit1;14required checks lack rebuilt catalog/detail-blob files,24are declared opt-ins. Do not mark local green or rebuild to bypass the hold. CI71de577f runs38694630261/38694625337 remain pending. Historical7ae CI38690059255 and38690055312 passed; those do not validate3a7b3143.

**Claude audit + two reference-free slices, October 15.**
- **CI fix.** CI on 583f014f failed: the config 1.25.0 fingerprint was missing, and 3 locked fixtures still expected the B7 mirror. Fixed in f5a2ef9a (tests only; the deltas are exactly the removed mirror). Display fixes:
  - cd398042: a dose finding reads "Not deducted here" even when the sixth pillar deducts for another reason.
  - 0018a811: removed the dead constant `safety_hygiene_over_ul_penalty`; it has no pipeline, app or website reader.
  - CI 38696611129 is green on 0018a811.
- **`probiotic_gate` (509d36fb, bded6e92).** Certainty and replication earn points only when applicability is above 0; the state is still taken from the ungated research. Across all 530 stored probiotic inputs:
  - 103 fall by exactly their Evidence change (mean −9.84).
  - No other pillar or state changes.
  - 41 tiers move from Needs improvement to Poor.
  - Canaries 184730, 76803 and 206362 were re-pinned by the gated certainty.
- **`blend` (f32c5ed4, be843285).** B5 alone owns blend opacity.
  - Removed the Dose `opaque_primary_sports_blend` and Formulation `sports_opaque_protein_blend` penalties and their registry keys.
  - B5 no longer withholds the complete-disclosure credit.
  - A hidden sports primary stays at Dose 0, with copy saying it is hidden.
  - A charged blend is always named in the headline. This also fixes 39 stored multis that said "fully disclosed".
  - Across 1,282 stored products: 309 rise (mean +5.87), none fall, 0 state changes, 102 tiers rise, 0 "fully transparent" headlines while B5 is charged.
- **Harness parity.** Per-product totals equal Codex's `verified_options.py` transforms applied alone: 530/530 and 1,282/1,282.
- **Note for completion guards.** A B5-charged blend now earns the disclosure credit (minus B5), while a plain row without a dose earns neither. Plain-row missing amounts must stay partial (101.36(c)), or a blend can beat an undosed row.
- **Focused tests.** 1,920 pass in the opacity owner/consumer files and 1,116 in the probiotic files. Fail-first nodes were shown for every behavior change.
- **Pre-existing local failures.** These fail identically on main 47c746537 against the corpus re-enriched on October 14 and are not caused by Step 4:
  - `test_v4_cross_module_canary_diversity` (4): 328825, 325587, 178346, 286725.
  - `test_v4_gate_canary_diversity` (3): 241706, 325587, 230149.
  - Causes are mixed (328825 lost a phytosome delivery credit; the probiotics have no delivery data). A separate task is proposed.

Next unchecked: production missing-data/completion and bound-aware dietary consumers; purpose/exposure and remaining approved owner/config cleanup (count/panel, disclosure, neutral, graded dose, unrated form, canonical probiotic, sixth-pillar move, source guards — must match the full harness scenario); probiotic copy; final measurements/review. Step4 remains unfinished. No main merge, rebuild or release.

## Current execution — V4.1 score accounting consolidation, October 14

Sean froze scoring policy and approved a five-step plan. Draft PRs: [PharmaGuide_Pipeline#144](https://github.com/seancheick/PharmaGuide_Pipeline/pull/144), branch `claude/score-ledger`, and the paired [Pharmaguide.ai#122](https://github.com/seancheick/Pharmaguide.ai/pull/122), branch `claude/score-receipts`. Nothing is merged, rebuilt or published.

Owner: quality_score.py::_build_pillars, module assessment owners, penalty_registry.py, scored_artifact.py; Flutter renders. Will NOT create: a scorer, registry, assessment or partial status, or ranking rule.

**Step 1 — matrix (documentation).** `scripts/audits/score_accounting_20261014/AUDIT.md`: 135 rows; all 114 corpus keys map to exactly one row. A fresh-context review checked 106 rows and found 18 defects, all corrected; Claude then checked the rest in code. A second review corrected the DUP-A rule, the authority-Evidence class and the causal counts, and added F17 and F19. Technical acceptance recorded below; current implementation authorization is in the leading entry.

**Step 2 — receipts and copy (behavioral public contract, zero score change).**
- Every scored pillar carries a `receipt` (AUDIT §8). Component kinds live in `penalty_registry.COMPONENT_KINDS`, and a receipt fails closed.
- Copy no longer claims what was not assessed. The sixth pillar keeps any dose finding visible.
- Fail-first tests: 16 receipt and 17 copy.
- 5,681 tests in every scorer-touching file pass. The 7 corpus-dependent cases pass with the corpus present.
- Re-assembling all 15,123 stored products: 0 deltas in totals, tiers, statuses, pillar score/max/components and Evidence states; every receipt reconciles; 0 remaining copy contradictions.
- Live clean main vs branch, 4,594 products from five brands: 0 deltas.
- Whole-fast CI 38648490506 is green on `e0d33c34f`.
- Local rung: 532 passed, 0 failed, 24 declared opt-in skips. Another 14 skips need a build directory that does not exist anywhere until the rebuild.
- Receipts add a median of about 2.4 KB per product to the blob.

**Independent acceptance — Codex, October 14.** Re-ran the stored corpus reconciliation: 15,123 scored / 69 suppressed / 234 not-scored inventoried; all scored receipts reconcile, zero numeric/state/component deltas or enumerated copy contradictions. Re-ran main versus candidate live scorer on the same 4,594 enriched products across BulkSupplements, Centrum, Thorne, Airborne and Culturelle: identical ID sets, totals, statuses, tiers, safety, pillar values/components and Evidence states. This does not establish delivery-context correctness or release readiness.

Rendered actual Flutter receipt widgets using five real candidate products (19028, 252349, 252413, 18174, 205211), all six expanded pillars, at 375-point width and normal/1.4 text scale; 60 layout captures pass. Inspected representative deduction/floor, neutral rounding, applicability-positive and unfinished-review renders. No rebuilt catalog or installed-device claim. Fixed app receipt rounding visibility (c9f2d99e) and unfinished Evidence capacity mislabeled Not earned (e9d12103), both fail-first. Latest focused app receipt/completion tests:18 pass; scoped analysis clean. Pipeline focused receipt/copy:33 pass. Whole-fast pipeline CI38648490506 passed runtime-equivalent e0d33c34f; latest app CI pending after e9d12103. Compact local evidence: reports/score_receipt_acceptance_20261014 in primary checkout. Steps 1–2 technically accepted for paired integration after applicable CI; Step 3 read-only measurements may start. No numerical policy, merge, rebuild or publication authorized by this receipt.

**App.**
- Awarded points now show under no-verdict states (104 products).
- Receipt rows render; the caption is fixed.
- Fixed: Compare showed a definitive tier for `partial` assessments.
- Tests: 7 new plus 1 fail-first. Full `flutter test` 3,922 passed; analyze clean.
- Candidate widget renders visually checked independently; installed-device/fresh catalog acceptance remains Step 5.

**Step 3 — corrected options.** See the leading entry and STEP3_OPTIONS.md; original B3 is superseded. Step3 closed October15; recommended option authorized and Step4 started. Rebuild/main merge/release remain held.

## Current execution — normal batch preflight/release repair, October 13


### October 14 — Meru unresolved fiber-source follow-up (candidate)

- Goal: fix sugar classification and phantom active count in canonical owners; independently assess score fairness. Baseline66c74be9. Behavioral pipeline change; no curated aliases removed or added.
- Owner: enhanced_normalizer.py::_process_single_ingredient_enhanced and enrich_supplements_v3.py dietary collectors; evidence: raw fiber row lineage and existing cleaner-role transparency exclusion. Will NOT create: another identity registry, form, status enum, or scoring rule.
- Fail-first: two source-role cases; two missing-sugar uncertainty cases; exact Dextrose and two existing alias controls. Native Meru71.3 vs60.7, counts4/4, sugar unassessed, diabetes_friendly false. Independent reviewer reproduced source controls and found no remaining blocker in this patch. Clinical Evidence overcredit remains a separate documented fairness gap;71.3 is not endorsed as clinically fair.
- Validation of runtime1d51e8d5:205 final owner/consumer tests pass;228 earlier related source-row tests pass; local546pass/24declared opt-in skips, skip guard green. Frozen111-label replay complete, source_unchanged true, exit0:110 unchanged; only Meru60.7→71.3. Baseline60ad17fa8 has identical runtime to66c74be9 (intervening changes are tests/docs only). Input manifest SHA256 fe70122a980c95649cd5a68ea71346c9ec9dff6ff1970eeeacb20478f9025091. Private receipts followup/{candidate.jsonl.meta.json,delta.json,UPDATED_RESULT.json,RESULT.md}. Final layer-A whole-fast CI38601675523 passed. PR142 remains draft, not integrated or released. No corpus rebuild; cleaner change requires Clean onward at the eventual integrated candidate checkpoint.

## 2026-10-14 — Meru clinical applicability, layer B (validated source candidate)

Owner: existing backed_clinical_studies and literature_evidence_records entries; clinical_applicability::assess_clinical_applicability; enrich_supplements_v3::_collect_delivery_data; normalization affirmative-match predicate; probiotic_formulation delivery consumer; evidence_resolver::INDICATION_KEYWORDS; scoring_input_contract::_classify_one; generic_evidence::_recover_contract_evidence_matches. Evidence: source matrix/glossary, live source APIs, fail-first regressions and frozen raw replay. Will NOT create: registry, public field/status, numerical scoring policy, product exception, deleted alias or deleted study.

Approved parser layer A is preserved: source1d51e8d5, CI38601675523 passed;111 labels,110 unchanged. Layer B retains all recognized aliases/studies, restricts PrimaVie and peppermint-oil evidence to the studied source preparation and purpose, corrects exact peppermint-oil UNII, and preserves affirmative source-bound delivery. Real-label review found and closed negation, cross-row probiotic credit, filtered source preparation, parallel clinical purposes and collagen-recovery metadata omissions at their existing owners. No scoring magnitudes changed.

Final behavioral source da1bc55fbb057a6f4fa2d7dd50e86990d6ad5b43: 1,458 final named owner/consumer tests pass; whole-fast CI38622739857 passes20,749 tests/192 declared skips with all four skip guards; local546 passes/24 declared opt-in skips with skip guard. Independent source and measured review closed with no remaining blocker. Six disjoint frozen sets total6,585 labels against baseline4ba03e8e, identical inputs, exit0/source_unchanged true.375 totals changed,6,210 unchanged;351 Formulation,23 Evidence,2 Dose movements (one overlap),63 tier movements. All explained by shared source/preparation/purpose fixes. Nine role-only diagnostics; no identity, amount, material, status, route, safety-gate, dose-safety or completeness changes. Three unrelated controls unchanged. Final recovery-only diff versus preceding candidate changes only269666, restoring its existing source-supported collagen evidence.

Meru:55.7/100 Needs improvement; Formulation13.3/20, Dose11.4/20, Evidence0/20, Transparency15/15, Verification6/15, Safety/Hygiene10/10. Evidence alone changes from accepted-parser71.3. Research remains visible; exact preparation/purpose applicability is unestablished. Dose includes disclosure-without-benchmark credit, Transparency is disclosure rather than label accuracy, Verification remains unknown, and Safety/Hygiene is catalog screening rather than personal safety or contaminant clearance. Existing0.2mL peppermint materiality and generic dose-wording limitations remain explicit; no invented density, numerical calibration or UI redesign.

Source and bounded measurement are complete, not integrated or released. PR142 remains draft. No full-corpus rebuild or public catalog publication. Concurrent main formulation-policy work needs integration reconciliation; then actual stage fingerprints and Clean-onward regeneration, catalog/app/release checks remain. Private primary-checkout receipts: reports/meru_shilajit_20261014/clinical/RESULT.md, FINAL_DELTA_REVIEW.json, accepted captures/sidecars and source receipts. Rejected captures are not acceptance evidence; compressed review reports and sidecar hashes remain, superseded bulk outputs and clean temporary baseline checkout removed.
