# B. Commit-by-commit review — index (413 commits on main, 2026-09-24 → 391b87c5)

Tiers: {'T3-docs': 44, 'T1-code': 153, 'T2-data': 129, 'T3-test-only': 17, 'T3-tooling': 28, 'T3-merge': 34, 'T3-other': 8}. Every commit has a row in `commits/classified.tsv` (sha, date, author, tier, files, subject). Tier 1 forensic records: `commits/T1_records.md`. Tier 2 data batches: `commits/T2_batches.tsv` (files, ±lines, body present, entry ids), `commits/T2_added_aliases.json`, `commits/T2_alias_holders.md` (every added alias resolved to its HEAD holder). Tier 3 (docs/tests/tooling/merges) are classified by their row only.

## Tier 3 rows

| sha | date | class | subject |
|---|---|---|---|
| 391b87c5 | 2026-09-28 | T3-docs | docs(register): Q36 is the BCAA ratio-source policy; Q37 label-text readers |
| dde22dab | 2026-09-28 | T3-docs | docs(register): Q36 resolved - generic BCAA names read the unspecified form |
| ff314096 | 2026-09-28 | T3-docs | docs(register): form curation after batch 11 (Q32, D21, Q35, Q36) |
| cb945215 | 2026-09-28 | T3-test-only | test(enrich): Kelp names iodine's kelp form since form curation batch 11 |
| 2f7339ad | 2026-09-28 | T3-docs | docs(register): form curation after batch 6 (Q32) |
| 9bdb896a | 2026-09-28 | T3-tooling | fix(submissions): integrator review findings on the agent reader and console auto-prep |
| 319f674d | 2026-09-28 | T3-merge | Merge the submission-transcription lane: agent reader, console auto-prep, product-submissions-prep s |
| faf426db | 2026-09-27 | T3-docs | docs(register): Codex lane audit and form curation status (D19-D21, Q32-Q34, R1) |
| 2f79050b | 2026-09-27 | T3-test-only | test: citation coverage reads tracked data only; the 299v canary reads the strain record |
| 0d4d59a6 | 2026-09-27 | T3-other | fix(release): contain verified form backlog |
| b059cd56 | 2026-09-27 | T3-test-only | test(scoring): freeze reviewed owner deltas |
| d3845a44 | 2026-09-27 | T3-test-only | test(forms): pin generic tocopherol weighting |
| af4dc08e | 2026-09-27 | T3-test-only | test(omega): align transparency canaries with native cap |
| 5f2915c4 | 2026-09-27 | T3-other | fix(clinical): allow explicit presence-risk dose context |
| 8b8360f4 | 2026-09-27 | T3-tooling | feat(submissions): agent_reader verify reads back what the reviewer will see |
| a04c5704 | 2026-09-27 | T3-tooling | feat(submissions): agent_reader sheet, and what the first live run taught the skill |
| b83231f8 | 2026-09-27 | T3-docs | docs(skills): product-submissions-prep replaces prepare-product-submissions |
| b59e5fdd | 2026-09-27 | T3-tooling | refactor(submissions): row parentage stays with the envelope; record asks it first |
| 05674bf5 | 2026-09-27 | T3-tooling | feat(console): opening a prepared submission leaves only the reviewer's clicks |
| b22770ca | 2026-09-27 | T3-tooling | feat(submissions): agent_reader files an agent's reading through the extractor |
| d2119e28 | 2026-09-27 | T3-tooling | feat(submissions): transcription-convention findings in checks.py |
| 2a2887f0 | 2026-09-27 | T3-tooling | fix(submissions): a loaded draft's statements carry notes, and every row names its missing ingredien |
| 5cb7716c | 2026-09-27 | T3-merge | Merge branch 'main' into codex/claude-177233-headline |
| 2a84da3d | 2026-09-27 | T3-docs | docs(harness): the fix loop runs the cheapest failing check first and the corpus once |
| 5af8f968 | 2026-09-27 | T3-merge | Merge remote-tracking branch 'origin/main' into codex/claude-177233-headline |
| 1201be02 | 2026-09-27 | T3-other | docs: round-two stale docs; the rollback playbook no longer promises a re-activation |
| b98b641c | 2026-09-27 | T3-test-only | test: drop count pins that only block data growth; one copy of each duplicate |
| 70dec135 | 2026-09-27 | T3-other | fix(data): a mistyped git ref fails the landed check instead of passing it |
| a3249ce7 | 2026-09-27 | T3-docs | docs(harness): batch by topic, verify per entry; data-fix and catalog-release in the repo |
| f6ed07bf | 2026-09-27 | T3-tooling | feat(replay): measure a data batch from raw labels, in parallel |
| 7b40e4dd | 2026-09-27 | T3-tooling | feat(verify): citation verifiers check only a batch's changed entries |
| ba23685e | 2026-09-27 | T3-tooling | fix(data): data-file writers write canonical JSON; format test reads tracked files |
| b6923c6a | 2026-09-27 | T3-other | feat(data): one batch helper for curated-data edits |
| 437aecb1 | 2026-09-27 | T3-docs | docs(audit): close final outstanding code findings |
| d173ca14 | 2026-09-27 | T3-test-only | test(export): require canonical serving basis |
| 9bd079ea | 2026-09-27 | T3-test-only | test(scoring): refresh omega transparency contracts |
| 7a26f2f8 | 2026-09-27 | T3-test-only | test(identity): preserve bitter orange dual classification |
| fa7f5c18 | 2026-09-27 | T3-merge | Merge remote-tracking branch 'origin/main' into codex/claude-177233-headline |
| 75164464 | 2026-09-27 | T3-docs | docs(audit): register records the v41 and identity-lane integration |
| 5185a0c0 | 2026-09-27 | T3-merge | Merge remote-tracking branch 'origin/main' into codex/claude-177233-headline |
| c5080f55 | 2026-09-27 | T3-test-only | test(iqm): preserve main coverage denominator |
| 106a8d59 | 2026-09-27 | T3-merge | Merge origin/main (Claude identity lane c0022415) into the v41 integration |
| 177eab34 | 2026-09-27 | T3-merge | Merge v41-recovery (Codex scoring/evidence recovery lane) into main |
| 974edb42 | 2026-09-27 | T3-merge | Merge current main into Claude identity lane |
| f7a58b2c | 2026-09-27 | T3-merge | Merge origin/main (Q18/Q25 identity splits, Q15 banned citations) |
| 19d9487b | 2026-09-27 | T3-merge | Merge remote-tracking branch 'origin/main' into claude/kind-newton-f2mz4l |
| a3abb199 | 2026-09-26 | T3-test-only | test(interaction): licorice hypertension flags unquantified blend children |
| 28d8e304 | 2026-09-26 | T3-docs | docs(audit): register records the green citation gates |
| 007f4e47 | 2026-09-27 | T3-test-only | test(safety): add the Mithras (33360) fixture the designer-steroid test reads |
| dd6a29e4 | 2026-09-26 | T3-merge | Merge remote-tracking branch 'origin/main' into claude/adoring-keller-9ab18a |
| 591a0c59 | 2026-09-26 | T3-docs | docs(audit): resolve Q23, Q24 and D18 with receipts; queue matcha identity (Q25) |
| 0edf0bb3 | 2026-09-26 | T3-docs | docs(rules): a studied dose is not a warning threshold |
| 05c3e5ad | 2026-09-26 | T3-tooling | fix(audit): citation fetch reads PubMed book records |
| 79cecfa1 | 2026-09-26 | T3-docs | docs(views): regenerate the interaction-rule views from the current rules |
| 0de250a2 | 2026-09-26 | T3-docs | docs(audit): close nutrition source acceptance |
| 36bbc5b2 | 2026-09-26 | T3-docs | docs(audit): D1b and D1c resolved; Q23 cleaner 0% DV and Q24 green tea severity |
| 5b8d7702 | 2026-09-26 | T3-docs | docs(audit): record final fast checkpoint |
| 7b055d5b | 2026-09-26 | T3-docs | docs(audit): record approved fiber source contract |
| f6c7d89d | 2026-09-26 | T3-docs | docs(audit): register the first full-coverage citation run |
| c11c2916 | 2026-09-26 | T3-tooling | fix(audit): backed-studies citation gate reads every citation in an entry |
| e349a2b7 | 2026-09-26 | T3-tooling | fix(audit): citation content verifier reads every citation in scripts/data |
| dafdf860 | 2026-09-26 | T3-merge | Merge remote-tracking branch 'origin/main' into v41-recovery |
| a875c626 | 2026-09-26 | T3-merge | Merge branch 'main' into v41-recovery |
| df89c74e | 2026-09-26 | T3-merge | Merge remote-tracking branch 'origin/main' into claude/adoring-keller-9ab18a |
| 00eabf5e | 2026-09-26 | T3-docs | docs(audit): register records Sean's D8 ruling and what it changed |
| becdcb4a | 2026-09-26 | T3-docs | docs(audit): record verified fiber source checkpoint and decisions |
| 52b275ea | 2026-09-26 | T3-docs | docs(audit): record P1's measured delta, identity notes and the stale local canary |
| 6767a383 | 2026-09-26 | T3-docs | docs(audit): record D1's measured delta and P1's landing |
| 0fa33340 | 2026-09-26 | T3-docs | docs(audit): register Sean's decisions, the C2 protein review and the Gemini-audit findings |
| 7260479a | 2026-09-26 | T3-docs | docs(audit): register the verifier coverage gap and the ghosts it hid |
| 50d99d9b | 2026-09-26 | T3-tooling | fix(audit): interaction-rules citation verifier reads dose floors and threshold notes |
| dc6313b8 | 2026-09-26 | T3-other | test(contracts): remove obsolete dose read exceptions |
| da77c456 | 2026-09-26 | T3-docs | docs(audit): register the pinned unlanded commits, app stashes and unreachable WIP |
| 7133937d | 2026-09-26 | T3-docs | docs(audit): one register of every pending item from the 2026-09-26 integration |
| d60cfc40 | 2026-09-26 | T3-docs | docs(audit): record release blockers and mixed-purpose policy probe |
| f3f75bcd | 2026-09-26 | T3-tooling | test(harness): keep corpus safety scans in artifact gates |
| 8dbd621b | 2026-09-26 | T3-docs | docs(audit): track the 2026-09-22 scoring diagnosis packet |
| 292f83fc | 2026-09-26 | T3-merge | Merge branch 'claude/b0-policy-signals' into integration |
| 0d410c84 | 2026-09-26 | T3-merge | Merge branch 'claude/verify-cui-prep-guard' into integration |
| f667c761 | 2026-09-26 | T3-merge | Merge branch 'claude/iqm-miroestrol-cui' into integration |
| ff5a812f | 2026-09-26 | T3-merge | Merge branch 'claude/iqm-phlorizin-cui' into integration |
| 19b44db4 | 2026-09-26 | T3-merge | Merge branch 'claude/mk677-fda-source' into integration |
| 3cbd6fe6 | 2026-09-26 | T3-merge | Merge branch 'claude/banned-cui-anchor-review' into integration |
| a4cc5c6b | 2026-09-26 | T3-test-only | test(dose): pin omega minimum exposure instead of endpoint average |
| d101baff | 2026-09-26 | T3-tooling | refactor(audit): cui_overrides.json is verify_cui's only override source |
| a5bc92b7 | 2026-09-26 | T3-merge | Merge branch 'v41-recovery' into integration |
| 51dd4afb | 2026-09-26 | T3-tooling | fix(audit): verify_cui rejects CUIs named for a product form the entry lacks |
| 69c08dbc | 2026-09-26 | T3-docs | docs(audit): record protein and omega acceptance results |
| b594cee0 | 2026-09-26 | T3-tooling | fix(audit): citation topic stems for the smoker and asbestos conditions |
| b3d4eb7c | 2026-09-26 | T3-merge | Merge branch 'claude/affectionate-euclid-47926a' into integration |
| e55de362 | 2026-09-26 | T3-merge | Merge branch 'claude/elegant-proskuriakova-54f9b7' into integration |
| 26e9d733 | 2026-09-26 | T3-merge | Merge branch 'claude/banned-unii-alias-only-matches' into integration |
| 5efe5a9b | 2026-09-26 | T3-merge | Merge branch 'claude/fervent-zhukovsky-791ee1' into integration |
| d2c69094 | 2026-09-26 | T3-merge | Merge branch 'claude/xenodochial-yonath-ce0df1' into integration |
| 3a12e873 | 2026-09-26 | T3-merge | Merge branch 'claude/pensive-jones-c021db' into integration |
| 87529ab2 | 2026-09-26 | T3-merge | Merge branch 'claude/practical-saha-38fbb3' into integration |
| 5ed85a1a | 2026-09-26 | T3-merge | Merge branch 'claude/heuristic-blackburn-a294f5' into integration |
| fffcd21f | 2026-09-26 | T3-merge | Merge PR #58 branch 'claude/angry-khayyam-155ede' into integration |
| 24133e0d | 2026-09-26 | T3-merge | Merge PR #59 branch 'claude/busy-hugle-008027' into integration |
| 0fd92bb9 | 2026-09-26 | T3-merge | Merge PR #60 branch 'claude/priceless-elgamal-691d42' into integration |
| 362aa338 | 2026-09-26 | T3-merge | Merge branch 'harness/ownership' into integration |
| 305329ac | 2026-09-26 | T3-test-only | test(safety): pin the laxogenin gsrs block's DSLD fields, not only its name |
| d9ae0687 | 2026-09-26 | T3-tooling | feat(audit): interaction-rule Bookshelf citations must name the rule's subject |
| 4c59e795 | 2026-09-26 | T3-tooling | fix(verify_unii): confirm a curated UNII whose GSRS record carries the entry's name |
| 93942c04 | 2026-09-26 | T3-tooling | fix(verify_unii): set iteration order no longer decides the name-match verdict |
| f834caa5 | 2026-09-26 | T3-docs | docs(audit): laxative receipts quote LiverTox tolerability, EMA 5.3 and the casanthranol gap |
| 304e6e57 | 2026-09-26 | T3-tooling | fix(audit): common English words no longer satisfy the citation subject check |
| 6b4522a8 | 2026-09-25 | T3-test-only | test(scoring): align contracts with calibrated rubric |
| b1dbe9d1 | 2026-09-25 | T3-tooling | feat(audit): interaction-rule citations must match their sub-rule's subject and topic |
| a550b8e3 | 2026-09-25 | T3-docs | docs(audit): classify the ingredient-row twins and record the evidence |
| aa394463 | 2026-09-25 | T3-tooling | fix(audit): read the blob's standard_name in the safety-separation audit |
| 8c6a2797 | 2026-09-25 | T3-docs | docs(audit): record the row-twin follow-up classification and evidence |
| a6ef1e74 | 2026-09-25 | T3-test-only | test: run the vitamin-A unit audit test against the production check |
| 1c8b3457 | 2026-09-25 | T3-test-only | test(immune): pin the Dose band edges, the strict high-dose thresholds and the at-cap sum |
| b3191f62 | 2026-09-25 | T3-docs | docs(release): record the interaction hydration pin as part of the bundle |
| bc633dab | 2026-09-25 | T3-docs | docs(export): record the retired row twins and the row-shape gate |
| ab4e1eca | 2026-09-25 | T3-docs | docs(agents): every agent records its lane in its worktree handoff |
| 56026a35 | 2026-09-25 | T3-docs | docs(skill): add /pg-scoring-change; move the measuring procedure out of the scoring rule |
| b7317904 | 2026-09-25 | T3-docs | docs(audit): census undeclared ingredient-row blob keys (report only) |
| 9d0ccc8e | 2026-09-25 | T3-docs | docs(adr): record one public scorer, IQM form ownership, one owner per decision |
| 281d3b97 | 2026-09-25 | T3-merge | Merge remote-tracking branch 'origin/main' into v41-recovery |
| 001bcad8 | 2026-09-25 | T3-other | docs(harness): load AGENTS.md every session; scope rules by path; one brain across repos |
| c521380b | 2026-09-25 | T3-docs | docs(ledger): record the cert and UL owner integration onto v41-recovery |
| 4cf582b1 | 2026-09-24 | T3-tooling | fix(replay): name a pillar aggregation change instead of calling it unattributed |
| 24dc229b | 2026-09-24 | T3-tooling | feat(replay): read-only calibration report over frozen snapshots |
| daaff8b1 | 2026-09-24 | T3-docs | docs(v41): A4 was not ported and P4 is ported under Dr. Pham's approval |
| e3d36f2c | 2026-09-24 | T3-other | fix(audit): the contract-leak gate classifies every raw read and passes honestly |
| 30af5396 | 2026-09-24 | T3-docs | docs(v41): record A13-P4, the one-brain consolidations and the full integration comparison |
| 108b7e53 | 2026-09-24 | T3-docs | docs(v41): record the final Task 2, harness and FiberSMART commits and the tracked follow-ups |
| de63b205 | 2026-09-24 | T3-tooling | feat(tooling): the production A/B harness records route, eligibility, identity and exposure |
| b0b06053 | 2026-09-24 | T3-docs | docs(v41): record the B5, B1, B3 and Task 2 ports with their validation |

## Tier 2 data-batch records (spot checks: three or more added aliases per batch resolved to their HEAD holder and read for chemistry)

| batch | commits | entries | spot-check result | class |
|---|---|---|---|---|
| Form curation b1 phosphate salts | 44948004 | 12 aliases (monobasic calcium/sodium/potassium phosphates → monocalcium phosphate / phosphate salts) | chemistry consistent; f56d49eb later gave monocalcium phosphate the calcium-phosphate class absorption | VERIFIED_CORRECT |
| b2 chelates/glycinates/hydrates | a6a521c7 | 76 (Albion/TRAACS chelates, citrate hydrates, protein chelates → the parent's chelate/citrate/bisglycinate forms) | 40 read: all chemically consistent (e.g. trimagnesium dicitrate → magnesium citrate; zinc arginate → zinc amino acid chelate; chromium glycinate → chromium unspecified: conservative) | VERIFIED_CORRECT |
| b3 other-nutrient salts | 57bc0986 | 14 (ascorbates on vitamin C rows; calcium phosphate dibasic on calcium citrate rows as source clue) | consistent, parent-scoped | VERIFIED_CORRECT |
| b5 parent-scoped clues | 852adda2 | 30 (R5P, P5P spellings, tocotrienols) | consistent | VERIFIED_CORRECT |
| b6 held spellings | 64e27094 | 16 (5-MTHF glucosamine salt spellings, tocopherol isomers, chlorophyllin) | consistent; the glucosamine-salt strings were later removed (845d17c5) — resolved at HEAD as "not found", consistent with the register | VERIFIED_CORRECT |
| b7 carotenoids | 1c3b27ce | 20 | consistent; gamma-carotene scoped to vitamin A (845d17c5) | VERIFIED_CORRECT |
| b8 mineral salts | c8147f8d | 120 | 40 read: consistent; note calcium silicate / laurate / stearate / undecylenate → calcium (unspecified) as *source clues* under the calcium parent (an excipient row read as a calcium form when the row is an active — see d36b6052/0433c386 for the active/excipient split); dolomite → magnesium carbonate (Ca-Mg carbonate; acceptable) | VERIFIED_CORRECT with 1 policy note |
| b10 vitamins/aminos/botanicals | d6dbf0e4 | 146 | 40 read: consistent; **`k2` → `vitamin k (unspecified)` source clue under `vitamin_k`** deserves a look (vitamin K2 is its own parent `vitamin_k2`; a "Vitamin K (as K2)" row would read unspecified K) → T2 note, verify on the label that carried it | CORRECT_BUT_NEEDS_MORE_VALIDATION (one alias) |
| b11 seaweed iodine + binomials | 00303a69 | 44 | consistent (kelp/bladderwrack/Ascophyllum/Fucus → kelp iodine; binomials as source clues) | VERIFIED_CORRECT |
| f8241717 blocked disclosures, 889856ef, 84ec8398 | data | empty bodies | not spot-checked | CORRECT_BUT_NEEDS_MORE_VALIDATION |
| 654e5034 / d36b6052 / 28178b54 / 863deb0f identity batches | data + code | live-verified identifiers named in bodies (UNII/CID); resistant dextrin form; FiberSMART aliases | consistent with the test docstrings at HEAD | VERIFIED_CORRECT |
| Interaction-rule citation batch (≈60 commits 2026-09-26, D6/D8) | data | each commit names the PMID and what the source says; `--strict` gate passes | not re-verified against PubMed in this pass (the gate ran in the suite) | CORRECT_BUT_NEEDS_MORE_VALIDATION (sampling deferred) |
| Banned/recalled anchors (3315ebee 36 records, SARM/MK-677/laxogenin/tansy/chaparral, Cape aloe, cascara, senna/frangula/rhubarb watchlist) | data | bodies cite FDA letters / eCFR / EU court docket | Cape aloe EU status sentence read and consistent with T-189/21 | CORRECT_BUT_NEEDS_MORE_VALIDATION |
| B12 governance (70a24eee, 7dbd1447, 2be4e59d) | data | RR-02 | — | NEEDS_HUMAN_POLICY_DECISION |
| Canonical-JSON rewrites (6ef5c1f9, 7af59d6a), metadata recount (9fc80c24), fixture bytes (f3b23bfb) | data | content-neutral by construction (`data_batch.py` canonical form) | — | VERIFIED_CORRECT |
