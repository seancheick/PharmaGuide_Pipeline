# Pending items register, 2026-09-26

One register for every open item found by the 2026-09-26 integration: the 25 lane handoffs (archived
under `~/claude-attic/2026-09-26/worktree-state/`), the memory open-work index, Codex's v41 handoff and
live API checks. Duplicates are merged. Every row was re-checked against pipeline main 8dbd621b and
app main af472e5 on 2026-09-26; nothing here is carried forward from a handoff unverified.
Evidence receipts for the data fixes: `research.md` in this folder.

Close an item by editing this file in the commit that resolves it.

## P1: safety

| # | Item | Evidence | Owner / next |
|---|---|---|---|
| P1 | Botanical identities silence the IQM twin's interaction rules: ~94 shipped products under-warned (garlic_bulb/black_garlic 24 of 31, lion_s_mane 30/30, boswellia_serrata_resin 12/12, reishi_mushroom 8/8, dandelion_root 7/7, 13 more with 1-3). | Census over `scripts/final_db_output/detail_blobs` (catalog 2026.09.22.201915); 184004 has an active 320 mg garlic bulb row and 0 garlic warnings. `_collect_interaction_profile` keys rules by (db, canonical_id); `identity/interaction.py::interaction_subject_ids` expands only IQM subjects. | Spawned task task_b9ea39ba: verify each pair (species + part), extend `identity/interaction.py`, measure through `enrich_product`, Sean decides landing. Independent of D1. |

## Decisions for Sean (evidence recorded, nothing changed)

| # | Decision | Current data (verified 2026-09-26) |
|---|---|---|
| D1 | Should IQM interaction rules fire on non-scorable (blend-child) IQM rows? Options A keep / B all non-scorable label rows / C blend children / D presence-only. | Census kept in worktree `.claude/worktrees/objective-bhabha-0235e6/.claude/state/blend_child_interaction_census/`. |
| D2 | Buckthorn identity: Rhamnus cathartica vs Frangula for labels DSLD groups as Frangula (17192, Laxaherb 241318/275837). | Report: `~/claude-attic/2026-09-26/worktree-state/elegant-proskuriakova-54f9b7/.claude/state/buckthorn_identity_report.md`. |
| D3 | banned_recalled identity anchors: BANNED_EPHEDRA UNII GN83C131XS (ephedrine) vs plant; RISK_KAVA W1ES06373M (kavain) vs root; RISK_GARCINIA_CAMBOGIA 8W94T9026R (HCA, shared with IQM) vs fruit; BANNED_ACONITE QU71159N2W (one species) vs governed null. BANNED_PENNYROYAL, BANNED_TANSY, HIGH_RISK_CHAPARRAL have no UNII and no unii_status, so `verify_unii --apply` would write oil UNIIs. | Options with GSRS names: archived handoff `banned-unii-alias-only-matches`. |
| D4 | Laxogenin: bare "laxogenin" and "laxogenin acetate" are still aliases of ADD_5A_HYDROXY_LAXOGENIN; its reason says "A steroidal plant compound" while inactive_policy_reason says "Synthetic anabolic". | FDA WL 622337 and the 2022-05-09 constituent update call it not a dietary ingredient; neither calls it plant-derived. |
| D5 | Anthraquinone laxative class: senna pregnancy/lactation is caution/caution while EU monographs contraindicate; senna and cascara cardiac_glycosides are avoid/established while EMA 4.4 says consult a doctor; split casanthranol (3SJ3U7J6V2) out of ADD_CASCARA_SAGRADA; approve the cascara inactive-policy reversal and softened liver action. | `RULE_IQM_SENNA_PREGNANCY`, `RULE_IQM_CASCARA_SAGRADA_PREGNANCY`, `ADD_CASCARA_SAGRADA`. |
| D6 | Wire `verify_interaction_rules_citations.py --strict` into `scripts/test.sh release` and `release_full.sh` (lanes recommend yes). | `--strict` PASS on main: 233 PMIDs + 16 Bookshelf chapters, 65 reviewed, 0 not found. |
| D7 | Severities resting on weak or extrapolated evidence: bergamot avoid/contraindicated, andrographis autoimmune caution, rhodiola sedatives, L-theanine sedatives, willow surgery avoid. Possible under-warning: willow bark pregnancy/lactation is no_data/no_data while the EU monograph contraindicates third-trimester use. | Triage receipts: `scripts/audits/interaction_rules/citation_triage_2026_09/research.md`. |
| D8 | Dose floors their cited abstract does not support: RULE_IQM_CHONDROITIN 1200 mg/day while the source escalated to 1200 mg twice daily; RULE_IQM_BLACK_SEED_OIL_DIABETES 2000 mg/day labelled documented_effective_dose while the meta-analysis reports no dose association. | `research.md` in this folder. |
| D9 | RULE_IQM_ALOE_FEROX liver sub-rule cites LiverTox's Aloe vera record for Aloe ferox (agent-reviewed class-level citation, 2d086156). | `interaction_rules_ghost_review.json`. |
| D10 | SARM_ANDARINE, SARM_CARDARINE, SARM_LIGANDROL, SARM_OSTARINE, SARM_RAD140 (2017-10-31) and RECALLED_TITAN_SARMS_LLC (2025-12-12) label a warning-letter date "FDA ban effective", the pattern rejected for MK-677. | `banned_recalled_ingredients.json` regulatory_date_label. |
| D11 | IQM miroestrol carries a hand-authored gsrs block although GSRS has no record (search: 0 results). | `research.md`. |
| D12 | Scoring policy: product-level penalties at equal public points in every rubric; sugar gram thresholds and basis; B1 active-row charges absent from inactive_penalty_details; one B0 charge per rule across rows (b0 lane); shared Dose/Formulation fiber-type classifier (moves 34 products); 9 never-emitted FIBER_CANONICALS; mixed-purpose ownership (Codex). | Archived handoffs magical-carson, b0-policy-signals, priceless-elgamal; Codex v41 handoff. |
| D13 | verify_cui IQM mode ignores forms[].aliases: 13 of 15 IQM MISMATCHes are false positives, but widening would accept loose matches. common_bean_extract C4321296 and brown_kelp C0022980 verified correct anchors today. | Archived handoff iqm-phlorizin-cui. |
| D14 | Export schema 3: drop the legacy NULL columns and the score_100_equivalent mirrors (cross-repo contract). | `core_export_model.py::_SCHEMA3_REMOVED_COLUMNS`. |
| D15 | Reviewer benchmark v7: treatment of PHAM's 23 exposed rows; ratify AMENDMENT_1.1.1. | `scripts/audits/v4_reviewer_benchmark/pending_v7/`. |
| D16 | B-complex Formulation structure (panel 10 + form + focus + disclosure, cap 23). | `b_complex.py`. |
| D17 | Vinpocetine approval is recorded as the project owner's, not a named clinician's; confirm that suffices. BANNED_HIGENAMINE reason wording unverified. | `test_cross_db_overlap_guard.py` (d217c765). |

## Queued work with an owner (agent work, not started)

| # | Item | Evidence / owner |
|---|---|---|
| Q1 | 75 IQM parents carry "No RxNorm concept found via GSRS lookup"; RxNav name search matches 22 of them, many to a different concept (yohimbe -> yohimbine, colostrum -> human colostrum, senna -> sennosides USP). One-entry review each via /data-fix; never bulk-fill. | Probe 2026-09-26; cascara fixed (e69e1223). |
| Q2 | Safety matcher findings: duplicate bitter-orange entries; limit-spec forms ("<1 ppm" in prefix or notes) match in gate and export; enricher row-level negative veto vs resolver term-level veto. | Archived handoff elegant-proskuriakova. |
| Q3 | Fiber/sports formulation: sugar+sweetener copies of the shared owner (~456 products), fiber detox counted twice, laxative up to 4x, fiber component literals not in config. Coordinate with Codex, who is working generic/fiber Evidence and Dose. | Archived handoffs magical-carson, heuristic-blackburn. |
| Q4 | Cassia seed (C. obtusifolia / C. tora) anthraquinones not reviewed. | Archived handoff anthraquinone-laxative-curation. |
| Q5 | Unsourced mechanism sentences: DSI_WAR_GARLIC "mild CYP2C9 inhibition"; RULE_IQM_CHONDROITIN anticoagulant "vitamin K-dependent clotting factors or antithrombin III". | `research.md`. |
| Q6 | 11 partial citation matches from `verify_all_citations_content.py` (ingredient-correct, adjacent topic; DEP_BETABLOCKERS_COQ10 stays suppressed). None is a wrong-ingredient citation. | Report: 491 match, 0 mismatch. |
| Q7 | Med-nutrient: 29 needs_revision records (4 strong ones suppressed on procedure, 6 never reviewed, ~19 evidence defects) incl. DEP_ANTICONVULSANTS_BIOTIN; sections 05 and 06 lack research.md; verified -> publication_ready enum migration deferred. | memory project_b1_suppressed_records_triage, project_med_nutrient_section_audits. |
| Q8 | Label facts shipping empty or thin: NCFM strain cites a mouse study (clinical review), "Labdoor Certified" unmatched, black_pepper_extract has no piperine crosswalk, cleaner still parses allergenFree lists. | memory project_silent_empty_fields_2026_09_16. |
| Q9 | Smart flagging phases 5-6 (timing rollup, co-formulation grouping) and D3/D4 (missing-serving fail-open; summaries ignoring dose_floor_status). | memory project_smart_flagging_rework. |
| Q10 | Submissions: 60-product development/holdout set not assembled; 178392 label_mismatch correction unverified. | memory project_submission_foundations_batch1, project_submission_batch_2026_09_11. |
| Q11 | Phase 4 follow-up: pregnancy/caffeine materiality is still presence. | memory project_phase4_reconciliation_authoring. |
| Q12 | Metformin/B12 softened consumer copy stays parked until a B1 delta re-review. | memory project_batch01_metformin_softening_parked. |
| Q13 | Unlanded July/August work that survived only as unreachable git objects, now pinned by local tags (not pushed): `archive/unlanded-label-trust-nested-nutrients-02f4686f` (07-20, build_final_db nested nutrient components + 4 tests; 0 of the 4 tests and 4 of 5 helpers are absent on main, which ships display_ingredients / label_ledger_* instead, so it may be superseded), `archive/stash-pre-label-hierarchy-scoring-2b45bf72` (07-20 stash), `archive/stash-bcaa-evidence-wip-153d63af` (08-06 stash: backed_clinical_studies, enricher, generic_evidence). Review each against main; delete the tag once decided. | `git fsck --unreachable` 2026-09-26. |

## Codex lane (v41-recovery, active)

| # | Item |
|---|---|
| C1 | v41-recovery is ahead of main and must merge main 8dbd621b. Expected conflicts: quality_score.json version, fingerprint history, test_v4_config_registry; take a version above 1.21.2 and keep every ledger entry. Codex's handoff still says main is unpushed. |
| C2 | 14 protein products lost unsupported Evidence credit; source-family evidence review before any release. |
| C3 | Older v41 notes: botanical dosing basis (extract vs marker ranges; curcumin phytosome, milk thistle) and folic-acid prenatals without a folate evidence match. Verify in the Codex lane. |
| C4 | 245 unreachable commits include Codex WIP stashes from 2026-09-22 to 09-25 on v41-recovery and codex/product-quality-redesign. Git prunes unreachable objects after its expiry window; Codex should confirm none holds unapplied work. |

## App repo

| # | Item |
|---|---|
| A1 | 7 golden tests fail from glyph rasterization drift on this machine (0.06-0.07% of pixels, text edges only, layout identical): nutrient_progress_bar x2, hero_section, probiotic_section x2, med_nutrient_reviewer x2. Regenerate in the canonical Flutter environment. |
| A2 | Two app stashes of other owners: stash@{0} "codex batch1 frozen submission docs" (2026-08-25), stash@{1} "pre-existing local changes before label hierarchy integration" (2026-07-20, 6 files). Owner decides keep or drop. |

## Release-time (only with a release)

| # | Item |
|---|---|
| R1 | Full-corpus re-enrichment (data edits trip the freshness gate), then `scripts/test.sh release`, the laxative verdict probes, and roll `reports/baseline_pre_e1_2_2` forward for the retired row keys. |

## Closed on 2026-09-26

Landed on main 8dbd621b and pushed: multi-form Dose bonus retired; fiber identity matrix entry;
row twins and zero-reader row keys retired with the row-shape gate (app readers removed, af472e5);
immune magnitudes in config; interaction DB published and app pin 1.0.12 (af472e5); cascara/senna ghost
PMIDs and 32 re-sourced rules with the strict citation gate; verify_unii and verify_cui fixes;
laxogenin, NPDMA, tansy, ephedra, chaparral, mk677, phlorizin and miroestrol identifiers; anthraquinone
laxatives in banned_recalled with enricher/gate parity; B0 and Safety/Hygiene on the gate's
policy-filtered concerns; Codex's Candidate D calibration through 69c08dbc; PRs #58, #59, #60.
This branch: cascara rxcui 66869 and miroestrol class (e69e1223); chondroitin, black seed and evening
primrose copy (a70e057d); garlic-warfarin ghost PMID (f7a10389); CoQ10 source label (786d318b); matrix
consumers (ff1793cb). App: med-nutrient parity pin repinned to the bundled artifact (4c5ff2b).
Sessions: finished and stale PharmaGuide sessions archived; kept: the blend-child decision (D1), "Product quality redesign implementation" and the running "Audit Gemini and leftover work".
