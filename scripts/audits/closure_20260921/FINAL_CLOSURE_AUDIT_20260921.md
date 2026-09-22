# Final closure audit — Evidence / scoring / depletion / pipeline (2026-09-21)

Scope: Phase 0 → the final closure commit **`b5d6d859`** (base `d70fd740`; closure commits `2d071d2b`
round 1, `2d7d4ea8` round 2, `b5d6d859` round 3; later commits touch this report only), the Gemini WIP left dirty
on top of it, the Buff/peer Phase-3 lineage, archive tags and unreachable commits
(forensic evidence only). Every claim below was reproduced on real artifacts;
the command or test that proves it is named beside it.

## 0. Run results

**Status: round-3 probiotic replay complete (1,308 labels, below); the final full production run
(37 brands, 15,414 labels, then the submission lane) is pending on `b5d6d859`.** Every
code change below lands before it; the release sequence (37 brands → submission lane → reconcile → snapshot →
strict gates → release tier → `release_full.sh` → post-release checks) runs on
the final code and fills this section. Nothing here is claimed from tests alone.

Pre-run evidence already on real artifacts (C1 = the last full 37-brand run):

| Claim | Proof |
|---|---|
| Dead-code / dead-field removals are score-neutral | B1 → C1 full corpus: 0 movers (pillars, totals, status, assessment, verdict, evidence/display state, tier, rules); raw → clean → enrich → score on 395 sampled products with the final code: 0 movers |
| §2 #17 (probiotic completeness) moves only assessment status | same-input A/B, C1 enriched → final scorer, 15,421 products: 0 score / pillar / verdict / tier movers; 185 complete → partial (142 probiotic route, 33 other routes, 10 reviewed-null); 186 Evidence explanations changed (the 185 + 307569, which carries credit beside an unresolved active) |
| No product is `complete` while an assessable active is open | corpus check against the final resolver: C1 had 185 such products; the final scorer moves all 185 to partial → 0 remain. (The old resolver, which treated an open strain review as terminal, saw only 297589.) |
| Export changes are the intended ones | C1 export vs final-code export on the same scored inputs, 15,310 blobs: `ingredients` 3,310 (label ledger), warnings 305 (276 duplicate cards removed, 0 rule sets changed), `banned_substance_detail` 2 |
| Blob contract | final-code export: 0 RED, 0 undeclared top-level keys; D5.3, D5.4, label-fidelity, safety-copy artifact tests 32/32 (7 fail on the C1 export) |
| Evidence universe (C1 inputs, final resolver) | 97,274 assessable active rows in 926 canonicals; 95,365 terminal (98.04%); 1,909 open = 1,900 probiotic rows in products holding an open strain review + 5 "Bulgarian Yogurt Concentrate" rows (literature search required) + 4 identity-unresolved rows (307560 ×2, 307569, 81801). Products: 15,118 complete, 303 open (295 strain review; 5 strain review + yogurt concentrate; 3 identity). Caveat: the resolver's probiotic owner is product-scoped, so in a product held by a stub even a reviewed strain's row (e.g. LGG) reads open — product completeness is exact, per-row open counts are an upper bound |
| Counts reconcile | C1: 15,414 raw labels in 37 brands − 2 with no ingredient rows in DSLD (250356, 312659 → Cleaner `incomplete/`, source limitation) + 9 approved submissions = 15,421 cleaned = enriched = scored = 15,310 shipped + 111 quarantined; no id in two outputs (no stale artifact can override a fresh one); submissions enter only through hash-verified human approval (`product_submission_import.py`); the two June `RITUAL_*.json` test labels sit outside `product_submissions/` and appear in no output |

Round 2 (2026-09-22, decisions D1–D9 resolved; §7). Full chain raw → clean → enrich → score on the
round-2 code for all 15,414 brand labels (0 errors), compared with the C1 scored artifacts:

| Claim | Proof |
|---|---|
| Every score mover is attributed | 174 movers (44 up, 130 down), 0 status changes: D5 applicability gate 119 (−0.3 … −1.5, Evidence only); D4 re-route 11 (+7.4 … +23.8); D1/D2 probiotic 33 (+1.8 … +5.1: CRL1505 mixed, I-3799 positive, Bl-04 now owned by its approved human RCTs, one positive primary outcome 34062085 + one null); D8 glucoamylase form 10 (−0.1 … −0.3); D3 307569 (−0.9) |
| Shipped partials 118 → 56, every one explained | 37 Bi-07 and 16 BB-12 (suspended clinician sign-offs) + the two LA-5 contexts held `adjudication_required` on 09-14 (2 more), + 307560 (source limitation, §6b). 109 `not_scored` are quarantined by the export gate, never shipped |
| Enzyme identity split is score-neutral | 183 labels with pectinase / hemicellulase / xylanase / beta-glucanase / DigeZyme / fungal protease: 0 score, pillar or state changes |
| Blend-total member fix (§2 #33) | 58 labels with a comma-joined blend total carrying member rows: 5 change — 259484 36.3 → 72.5 (EPA 1.5 g + DHA 500 mg were shipped at 0 mg), 231416 79.4 → 70.0 (EPA+DHA had been counted as 1,418 mg on a 500 mg label), 3 evidence-state only |
| Tests | fast tier 16,126 passed; slow tier 51 → 31, the remainder corpus-dependent (§3b, D9) |

Round 3 (2026-09-22, Dr Pham's review, the Codex audit and the second review; §2 #37–#41). Same-input replay of
the 1,308 raw labels that name a probiotic organism, raw → clean → enrich → score. Base: round-2 commit
`2d7d4ea8`; compared: the round-3 tree, whose pipeline code and data were committed unchanged as the final closure
commit `b5d6d859` (the replay started 11:39:57 after the last code/data edit at 11:38:55; only the review packet's text
changed after it):

| Claim | Proof |
|---|---|
| Shipped probiotic partials 55 → 0 | 55 partial → complete (F1 closed); the one remaining partial (78355) is `not_scored` in every run and quarantined, never shipped |
| Every score mover is attributed | 225 movers, all down, Evidence pillar only; each traced to a strain-row change, 0 unexplained: LGG 102, S. boulardii 16, 299v 10 (strong → medium); HN001 15, IS-2 18, MTCC 5856 9, M18 3, SNZ 1969 3 (positive result secondary, within-group or a ranking: 0.85); BB536 31 and M-16V 10 (surrogate-only / combination: 0); LA-5 6, RC-14 4, GBI-30 1 (withdrawn or surrogate); Bl-04, NCFM, BB-12, La-14 rows surface when the strongest row drops (BB-12 4.8 from its infant-colic RCTs) |
| No safety change | Safety verdict changes = 0: no product enters or leaves CAUTION, UNSAFE or BLOCKED, and 0 `quality_score_status` or route movers. The public `verdict` field also carries the quality verdict POOR, set only when `quality_tier` is the lowest tier (`scoring_v4/quality_score.py`, `v4_verdict`). 34 products move `verdict` SAFE → POOR, exactly the 34 whose `quality_tier` moves Needs improvement → Poor; 8 more move `quality_tier` Good → Needs improvement with `verdict` SAFE unchanged |
| Label-bounded scope | ATCC PTA 6475, CTV-05, 1714, CNCM I-745, B. clausii, Prodentis and MIMBb75 appear on no catalog label. HEAL9 and 8700:2 appear on two Nature's Bounty labels (240117, 62743) under their deposit numbers (DSM 15312, DSM 13434); both rows score 0 before and after, and those products' Evidence 8.0 → 6.0 is 299v (strong → medium). Corrected 2026-09-22: an earlier count searched for "HEAL9"/"8700" and missed the deposit names |
| Identity change 131 → 132 | New identity `STRAIN_BOULARDII_CNCM_I745`: the six CNCM I-745 study records moved off the species node `STRAIN_SACCHAROMYCES`, with the I-745 and Florastor aliases, so an unidentified *S. boulardii* label no longer inherits strain-specific evidence. Schema/identity change, 0 catalog products moved (no label names I-745 or Florastor). Registry after: 132 identities, 157 study records, 34 strain summaries (`test_cncm_i745_evidence_is_not_inherited_by_an_unidentified_boulardii_label`) |
| Nissle 1917 provenance | 15479682 recorded as human active-comparator equivalence evidence (medium, direction `unresolved`, no superiority credit). Verified against the PubMed abstract: design, 327 adults, 12 months, per-protocol relapse 36.4% vs 33.9%, equivalence p = 0.003. Tagged `reviewer_cited_not_independently_verified` in `PHAM_REVIEW_20260922.json`: the 20% margin, the one-sided CI bounds and the ITT rates (full text PMC1774300 not open access). The registry text states only the verified figures |
| Clinical registry frozen for the final run | After the registry self-audit below: git blob `81756b298404ca37eb49ca3229653cf08217346a`, sha256 `31ba1ed17b2433e3b3ff23eccf211311f4b030a5542c5ab7fbeb01643a1f7f22` (at `b5d6d859` it was blob `98083a87`). No evidence change until release; re-checked after the run. After release, a probiotic correction reopens this only if it is a P0/P1 correctness defect |
| Non-blocking follow-ups (Dr Pham) | (1) Countersign the 12 new study records. They score today under the 2026-09-14 owner convention: `review_status: clinician_approved` is the only scoring status, and `clinical_review.reviewer` names the actual approver, here "not a clinician sign-off". Of the 157 approved study records, 123 (approved 2026-09-14) and these 12 name the engineering owner as reviewer. The 18 D1 records also name the owner and carry Dr Pham's `countersigned_by`; the other 4 name her as reviewer. Each was checked against its live PubMed record; a countersignature replaces the reviewer string. (2) Confirm the M-16V anchor swap to 28796951 (null), the CTV-05 oral-route exclusion, ATCC PTA 6475 `mixed` and L. casei 431's strength after its source-type correction. M-16V (10 labels) and 431 (5 Solgar labels) are `null`, so they earn 0 credit whatever the strength; CTV-05 and ATCC PTA 6475 name no catalog label. (3) Set a scoring weight for active-comparator equivalence; Nissle earns none until then. None blocks this release (`CODEX_AUDIT_RESPONSE_20260922.json` `countersign_for_dr_pham`) |
| Tests | fast tier 16,212 passed, 0 failed; registry integrity 0 findings |

Registry self-audit (2026-09-22, reviewer items 9–10). The DATA was audited against Dr Pham's packet, not the
appliers: `pham_registry_reconcile_20260922.py` builds the per-strain table (identity, review status, her
decision, old → final citations, single vs combination, primary vs surrogate, direction, strength, eligibility,
points possible, sign-off, disposition) and fails on any mismatch. Table and dispositions:
`REGISTRY_SELF_AUDIT_20260922.json`.

| Claim | Proof |
|---|---|
| Every packet decision holds | 27 packet identities, 0 mismatches: Bi-07 and BB-12 released (Bi-07 0 points: acute crossover lactose challenge, breath-hydrogen surrogate); LA-5 + BB-12 combinations literal (`UNREGISTERED:` LC-01 / PRIMAL B. infantis) with zero component credit; her nulls 0 points; withdrawn citations absent from scoring; replacements present; CU1 wording pinned |
| Copies of owned facts corrected | `evidence_level` ≠ effective strength on 14 identities (now an integrity error); 6 case-duplicate aliases; indications of Bi-07, BB-12, HEAL9, 35624 and Nissle bound to their own evidence; `study_design` on the Bi-07 and BB-12 records (`registry_self_audit_20260922.py`, 27 asserted edits) |
| One-brain checks | 132 unique IDs; no alias under two parents; no two IDs for one strain; no duplicate context; no combination record in a derivation; one PMID in both a combination and a single-strain record, 33763399, a verified three-arm trial |
| Strain card agrees with direction | See §2 #42–#43: HN019 and 35624 had shipped "High support" beside null trials |
| Tests | `test_registry_self_audit_20260922.py` (incl. the audit as a standing gate) |


## 1. What the previous agent left, and what happened to it

| Gemini WIP item | Verdict | Evidence |
|---|---|---|
| Stage-2.4 validator accepts 4 new Cleaner roles | Kept, then consolidated: the role vocabulary had **4 drifting copies**; now one owner `constants.CLEANER_*_ROLES`. `inactive_non_scorable`/`review_required` removed (other fields' values). | `test_every_cleaner_role_literal_is_in_the_one_shared_vocabulary` |
| Enzyme IQM moves (serrapeptase, BioCore DPP-IV) | Kept and finished: plain DPP-IV aliases moved to `protease`, stale serrapeptase free text fixed, IQM `total_form_aliases` corrected (Gemini left it wrong). | d27 DPP pins fail on HEAD IQM, pass now |
| Probiotic "undisclosed CFU → terminal" (3 edits) | **Reverted.** It relabelled pending/rejected identity review as a dose gap and auto-completed unreviewed strains. Weak support earns 3 native points with no dose, so CFU never made those terminal. | 2 new tests fail on Gemini code, pass on revert |
| Analytical-fraction marker rule | **Narrowed.** Gemini's 40-term list broke a signed Phase-3 control (silymarin under a plain extract must stay active). Now: the directive's assay classes (polysaccharides, saponins, isoflavones, bile acids, total alkaloids), whole-label match, child ≤ parent mass, nested extract never a marker. | HEAD→now catalog: 7 row movers + 1 (Alkaloids); 0 HEAD markers lost |
| Snapshot 204571 64.2→59.0 "probiotic" | **False attribution.** Identical-input A/B: HEAD and WIP scorer both 59.0; the driver was the over-broad marker rule. With the rule reconciled the product is 64.2 again; fixture restored. | `chain_one.py` raw→score HEAD vs now |
| Snapshot 12012 not_scored→65.7 | Legitimate: committed HEAD code already gives 65.7; the fixture was stale. | raw→score on HEAD worktree |
| Snapshot rebuild failure (5 export errors) | **Real safety split-brain**, fixed (see §2 #1). | 5 products pass the parity assertion |

## 2. Defects found and fixed at their owner

| # | Defect | Owner fix | Proof |
|---|---|---|---|
| 1 | Inactive EDTA (liquid multis) flagged **banned** by the export while Stage 3 said SAFE; would ship `has_banned_substance=1` beside SAFE | `identity/safety.py` role-scope predicate used by resolver, Stage 3 and export | 5 real products; Phase-3 policy tests 37 pass |
| 2 | **Vitamin K1/K2 lost the warfarin caution** (live since 2026-07-28 identity split); MK-7 form rule never matched any form | `identity/interaction.py` interaction subject family, consulted by enricher profile + export `key_ingredient_tags`; MK-7 form_scope repaired | Doctor's Best MK-7 100 mcg: `interaction_summary` null → vitamin_k_antagonists; tags `[vitamin_k2, vitamin_k]` |
| 3 | Post-sum sports caps made public total ≠ pillar sum | Removed (decision A); validators require literal sum | `test_a_module_declared_cap_can_never_change_the_public_score` |
| 4 | `total > 0 → evaluated_applicable` leaked completeness for 33 products | Guarded; 32/33 closed at identity owners (silica provenance, `*_descriptor`, composition leaf, class-total marker, 4 IQM aliases) | `chain_ev.py` real-label chain |
| 5 | Probiotic review flag read "pending" for clinician-approved contexts | `context_review_finished` single owner; status reflects approval; points unchanged | NCFM 0, LA-5 6, LGG 8 unchanged |
| 6 | Scored artifact `_v4_*` overlay + `scoring_status` + `scoring_metadata` repeated ~18 facts | Consolidated (decision C) | `test_artifact_states_each_fact_once` |
| 7 | `share_title` truncated 74.6 → "74/100" while app shows 75 | `shipped_whole_score` | `test_share_title_shows_the_shipped_whole_score_not_a_truncation` |
| 8 | Dashboard depletion summary always 0 (wrong key) | key fix | `test_safety_copy_depletion_summary_reads_the_real_file_key` |
| 9 | `DSI_DIURETICS_POTASSIUM` mixed depletion prose into a safety rule; `DSI_BETABLOCK_MELATONIN` a benefit statement in the safety layer | Split: hyperkalemia only, scoped to potassium-sparing class (NIH ODS re-verified); melatonin rule retired to depletion owner (decision D) | `test_depletion_facts_have_one_owner_and_safety_warnings_stay` |
| 10 | `composition_leaf` rows entered the Evidence universe (third role-list copy) | `constants.CLEANER_NON_EFFICACY_ROLES` used by contract + resolver | `test_composition_leaf_never_enters_the_evidence_universe` |
| 11 | IQD dose-class vocabulary in 3 copies; validator copied identity dispositions | One owner each | `test_dose_class_and_identity_state_vocabularies_have_one_owner` |
| 12 | V3 husks in every blob: `section_breakdown` (0/25, 0/30, 0/20, 0/5), `omega3_detail`, V3-derived omega-3 bonus / blend penalty audit fields, a second copy of every `*_audit` under `audit.*`; dashboard "Score Trace" rendered the V3 math | Removed; audits keep only label facts (dose credit and blend penalty are pillar-owned) | 15,162-blob census: all zero; `test_blob_carries_no_v3_score_husks` |
| 13 | Phase-5 A/B switches, a resolver `except Exception` that silently let points mark a product complete, and an unknown evidence state rendering as "assessed" | Removed; display state cannot see points; undeclared state is `not_yet_reviewed`; resolver failure is loud | `test_legacy_score_inference_removed`, `test_resolver_failure_is_loud_not_a_silent_complete`, `test_undeclared_state_is_never_presented_as_assessed`; corpus: 0 resolver exceptions, 0 undeclared states |
| 14 | Scoring-input wiring: 45 reads of keys that exist on no product (dead aliases); `activity_value` misnamed (enricher writes `activity_quantity`); skipped-row "recovery" block that never runs on fresh artifacts; `omega3_detail` scorer fallback | Dead reads removed, misnamed key rewired, dead blocks removed | key census over 15,421 cleaned/enriched/scored artifacts; corpus line trace of `build_scored_artifact`; enzyme A/B on 90 products: 0 movers |
| 15 | Dead code: ~50 functions with zero references, 20 functions only tests called (their tests pinned dead code), 142 unused imports, `percentile_categories.json` (loaded, never read), temporary drift harness, V3 shadow diff, Phase-5 A/B tool | Removed. Test intents that mattered were ported to the live owner first (ephedra/DMAA/vacha/7-keto bans -> enricher; B7 over-UL rules -> shared `evaluate_dose_safety`; infantis strain codes -> `clinical_strain_identity_matches`; label-descriptor flags -> `InactiveIngredientResolver`) | fast suite after sweep, affected files green |
| 16 | Kept on proof of life (not removed): `allow_legacy_fallback` (the corpus trace shows `gate_safety` executing it), the safety normalizer's legacy flags/aliases (fail-closed quarantine for legacy shapes), the blob-shape goal path (audit-tool caller), `generic_trust`/`omega_trust` (lazy imports, live), dormant data-driven guards (`is_blocked` clinician REJECT/HOLD strains, stale-cert `scoring_blocked_reason`, policy holds, schema-2.x `migration_inference` quarantine) | Documented, not removed | trace + writer grep |
| 17 | **Probiotic review auto-terminalized by another strain's points.** The probiotic Evidence module checked `score > 0` / reviewed-null before the open-review gaps, and the resolver folded `native_research_review_incomplete` into the terminal `RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED`: a product holding an unreviewed registry stub (La-14, CUL-60, Lp-115, …) or a context awaiting clinician review shipped `complete` whenever a different strain earned credit. 297589 was the one product the corpus completeness check caught directly | Resolver: open strain review is `LITERATURE_RESOLUTION_REQUIRED` + blocker `probiotic_strain_review_incomplete` (no new state); one completeness helper `generic_evidence.evidence_completeness_gap` used by generic and probiotic Evidence; probiotic module checks gaps before any conclusion (studied whole formula still owns its evidence); silent `except Exception` fallback in the resolver's probiotic identity check removed; pillar copy for credit + open review | Same-input A/B over 15,421 products: **0** score / pillar / verdict / tier movers, **185** complete→partial (142 probiotic, 33 other routes, 10 reviewed-null); corpus invariant *complete ⇒ every assessable active terminal*: 0 violations; `test_one_strains_points_cannot_close_a_product_holding_an_unreviewed_strain`, `test_resolver_never_treats_an_open_strain_review_as_terminal` |
| 18 | Audit script `audit_inactive_safety` ran its own banned check without role scope (EDTA split-brain, third copy) | uses `identity.safety.safety_rule_out_of_role_scope` | audit agrees with Stage 3 and export on the 5 EDTA products |
| 19 | One hazard, two or three cards: critical warnings were keyed on the label spelling ("Yohimbe" + "Yohimbe bark extract" under `RISK_YOHIMBE`), and the safety-flag ban card dropped the entry's `ban_context`, so it never matched the substance-match card for the same rule | dedup subject = `matched_rule_id`; flag-path ban card carries `ban_context` from the same entry | C1 → final-code export: 276 duplicate cards removed on 259 products, **0 products lost or gained a rule**; `test_one_critical_card_per_rule`, `test_no_duplicate_warnings` |
| 20 | Projection rows took label text from the identity step, not the label: 5,619 rows (e.g. wheatgrass shown as "Couch Grass", Capsimax shown as "Capsicum") | label ledger (`display_ingredients`) owns the text; the identity owner's `normalize_label_display` gives the display form | 3,310 blobs changed; `test_projection_label_text_comes_from_the_label_ledger`, `test_label_display_name_drives_display_label`, Capsimax canaries |
| 21 | Match-ledger allergen and delivery domains iterated keys the enricher never writes → both empty on every product | wired to `allergen_hits` / `delivery_data.systems` | 126/126 and 82/82 sampled products now carry them; 0 score movers |
| 22 | Enricher `percentile_category_label/_source/_confidence/_signals`: compatibility copies for the retired V3 scorer, no reader in pipeline, dashboard or app | removed; the label ships from the scored artifact via `percentile_label_for` | field census; decorator tests retargeted |
| 23 | The resolver's five reference loaders (IQM, backed studies, therapeutic-dosing index, literature records, banned list) swallowed any error into an empty result: a malformed file would silently give banned ingredients evidence credit or turn every literature record into "resolution required" | loaders fail loudly; the probiotic identity check's `except Exception` heuristic fallback removed too | loader sizes identical on the real files (645 / 208 / 348 / 739 / 1,291); resolver, Phase-4 and integrity slice 2,751 passed |
| 24 | `literature_evidence_records.json` carried two case-variant duplicates (`NHA_TOTAL_BILE_ACIDS` / `nha_total_bile_acids`, `NHA_CONJUGATED_BILE_ACID` / `nha_conjugated_bile_acid`); the loader keeps the last, so the uppercase pair was shadowed and could drift unseen | shadowed pair removed one entry at a time; `total_entries` / `verified_records_count` 741 → 739 | resolver index unchanged (739 keys, same surviving records); 0 case duplicates left |
| 25 | **D1** 89 registry stubs (90 product-holding identities minus the two clinician holds, plus Ll-23) had no finished review, so 1,222 product-strain rows read "not yet reviewed" | One bounded literature batch: designation + species PubMed search, efetch XML (italic genus/species tokens preserved, which the 09-13 plain-text read lost), every candidate human record read. 15 strains → 18 single-strain placebo/vehicle-controlled contexts (uncontrolled and no-placebo studies listed, not scored, per the 09-14 convention); 74 → terminal `no_qualifying_human_evidence` with a reason (44 combination-only, 26 no human research, 2 uncontrolled only, 1 species conflict in sources, 1 combination-only with no product). Reviewer string names a delegated research review, never a clinician; `dr_pham_signoff` untouched. New terminal strain status `strain_reviewed_no_qualifying_human_evidence` (predicate `strain_literature_review_concluded`, which can never lift a clinician hold) | `scripts/audits/closure_20260921/d1_strain_review_20260922.py` + `D1_STRAIN_REVIEW_20260922.json` (per-strain query, screened PMIDs, classification); 0 unreviewed stubs left; `test_no_product_holding_stub_is_left_unreviewed`, `test_a_literature_review_never_lifts_a_clinician_hold` |
| 26 | Surrogate-only study evidence derived direction `null`, whose copy says the trial "did not show benefit for its primary outcome": false for NCIMB 30242, which lowered LDL in two RCTs | `derived_context_evidence` returns `unresolved` when no trial family reports a primary patient-important outcome (0 points; "benefit not established" copy) | no live strain derived null from surrogates before D1 (all four such derivations were shadowed by legacy blocks); `test_surrogate_only_contexts_are_unresolved_not_a_failed_trial` |
| 27 | **D2** Two owners of "is there human evidence": approved exact-strain human contexts vs a signed summary's `q3_human_clinical = NO` (NCFM, Bl-04, DE111) | Approved human contexts own human evidence over a preclinical summary; a signed human summary keeps ownership; a suspended sign-off stays under the clinician gate | Bl-04 +3.6 on its products (one positive, one null placebo RCT); `test_approved_human_contexts_own_human_evidence_over_a_preclinical_summary` |
| 28 | Agent-authored legacy summaries (BS01, LP01, M-63, four DS-01 members) duplicated owners; LP01's cited a two-strain vaginal study as strain-specific, DS-01's duplicated `FORMULA_SEED_DS01` | Retired into study contexts (BS01, M-63), a combination-only conclusion (LP01, whose unsupported `indication_primary` was cleared), or the whole-formula owner (DS-01) | same applier; DS-01 PMIDs 40944126 / 41750436 re-verified live |
| 29 | **D5** Evidence was dose-aware through a ×0.25 sub-clinical multiplier, a second owner of Dose | The guard is an applicability gate only: a sub-clinically dosed match earns 0 and the state is `applicability_unestablished`; multiplier removed from config (quality_score 1.13.0-dose-applicability-gate, fingerprinted) | 119 products −0.3 … −1.5 |
| 30 | **D4** "Multi + Probiotic" products with a full vitamin/mineral panel scored as probiotics | A title declaring a multi over a multi-eligible panel routes `multi_or_prenatal`; strains keep probiotic-owned disposition (no strain points, as on every non-probiotic route); "Multi-Strain Probiotic" titles unaffected | 11 re-routed (+7.4 … +23.8), 11 near-misses unchanged; `test_declared_multi_with_probiotic_adjunct_routes_multi_even_under_probiotic_taxonomy` |
| 31 | **D8** Chemically wrong enzyme parents: invertase/sucrase, maltase and phytase, then pectinase, hemicellulase/xylanase and beta-glucanase all under `cellulase` (C0007641); `pectinase` also owned by `digestive_enzymes`; the 2026-09-20 enzyme migration (`a8213c63`) dropped `digezyme`, bare `glucanase` and `protease, fungal` to unmapped | Own parents with live-verified CUIs (C0053409, C0002272, C0031853, C0032491, C0062220, C2365105) and PubMed-searched literature records; the three dropped aliases restored; IQM 5.5.6 | DSLD itself groups them separately (Hemicellulase 174 rows, Beta-Glucanase 160, Xylanase 139, Pectinase 132); 183 labels 0 movers; 19 slow alias pins now pass |
| 32 | **D3** 307569 citrus bioflavonoid source, 81801 Sytrinol PMFs, "Bulgarian Yogurt Concentrate" | Source-aware citrus bioflavonoid identity (generic name + citrus form); `citrus_polymethoxylated_flavones` parent registered narrower than `flavones`; yogurt concentrate is the dairy food `NHA_YOGURT_POWDER`, not the organism | 307569 and 81801 complete |
| 33 | **Live defect found by D9**: a comma-joined blend total that prints its members with amounts ("DHA, EPA 2 g Total" → EPA 1.5 g, DHA 500 mg) was treated as a decomposition leaf: its unquantified `forms` were expanded and its dosed member rows discarded. 259484 shipped EPA/DHA at 0 mg (36.3, Poor); 231416's EPA+DHA was counted as 1,418 mg on a 500 mg label | `_lift_decomposition_members`: at every nested-row loop, such a total is replaced by its members when each prints its own amount; totals whose members carry no amounts keep the leaf behavior | 58 affected labels, 5 change (§0); `test_blend_total_with_dosed_members_keeps_the_member_doses`, `test_blend_total_with_undosed_members_keeps_the_leaf_behavior` |
| 34 | Silent fallbacks: `router.class_for_product` returned `generic` on any classifier exception; the enricher fell back silently when classification failed | Both removed; the classifier is total on malformed input, so a failure is a defect and surfaces | routing slice 2,090 passed |
| 35 | **D6** The app's depletion card rendered Dart template sentences instead of the reviewed `alert_body` for four of five relationship types | App (`pg_depletion_card.dart`): the reviewed body is the card's clinical sentence; only the supply line (what the device sees in the stack) stays client-side; the details sheet's "Why" shows the mechanism | Flutter 872 stack/release-gate/signal tests pass; reviewer golden regenerated |
| 36 | **D7** 12 shipped blob sections have no reader | Kept in the 2.5.0 contract, marked `deprecated: schema_3` in `BLOB_TOP_LEVEL`, documented in `FINAL_EXPORT_SCHEMA_V1.md` | `test_deprecated_blob_sections_have_no_pipeline_reader` |
| 37 | **F1** Bi-07 / BB-12 clinician holds and two `adjudication_required` LA-5 + BB-12 trials kept 55 shipped products partial | Sent to Dr Pham on a review sheet; her decisions applied after live PubMed verification of all 35 PMIDs she cited: Bi-07 and BB-12 signed off (suspended summaries retired; the reviewed contexts own the evidence; Bi-07 surrogate-only, BB-12 adult trial null); 30439760 and 39102225 approved as literal three-strain records with an `UNREGISTERED:` component. One code change: `valid_native_study_context` accepts an unknown component only in a frozen record declaring `unregistered_components_present` | `pham_review_20260922.py` + `PHAM_REVIEW_20260922.json`; `test_pham_review_20260922.py`; 55 partial → complete on the 1,308-label replay |
| 38 | 23 strain sign-offs recorded in Dr Pham's name by an automated PMID check alone | She reviewed each: 12 confirmed (LGG, S. boulardii, 299v, HN001 recorded medium; Shirota, 35624 null), 5 replaced with direct human trials (SNZ 1969, M18, GBI-30 6086, ATCC PTA 6475, CTV-05), 6 withdrawn as single-strain evidence (HEAL9, GR-1, RC-14, R0052, R0175, LA-5) with an auditable `withdrawn_citation`. Three verifier fields that contradicted their own notes corrected; no sign-off in her name rests on an agent check | `test_no_signoff_in_her_name_rests_on_an_agent_check_alone` |
| 39 | **A strain summary with no `effect_direction` scored as fully positive** (`probiotic_evidence._effect_multiplier` defaulted to `positive_strong`): Shirota's and 35624's null evidence earned points | The probiotic scorer fails closed (generic Evidence already did); every one of the 34 strain summaries states a direction verified against its cited record; six source types mislabelled by the 2026-04-21 automated pass corrected (431 is a 1,104-person human RCT, DDS-1/UABla-12 had single-strain arms, 8700:2 / ME-3 / 1714 cite lab or review papers); Nissle recorded as human active-comparator equivalence evidence (no superiority credit until the scorer weights equivalence) | `test_every_strain_evidence_summary_states_its_direction`, `test_a_summary_without_a_direction_earns_no_evidence_credit`, `test_an_approved_context_outcome_without_a_direction_never_credits` |
| 40 | Codex registry audit (26 findings) and a second review (10) | Every claim reproduced live before applying: HEAL9 and LAFTI L10 "no evidence" conclusions came from incomplete searches (reopened with single-strain RCTs); DRACMA credited LGG's results to CRL431 + BB-12; M-16V carried a three-strain trial as NEC evidence (anchored to its strain-specific review, null); Prodentis aliased single strains to a two-strain blend; ATCC PTA 6475 omitted a 2-year null trial; CTV-05's vaginal efficacy reached oral labels; CNCM I-745 evidence split from the S. boulardii species node; indications and benefit claims bound to their records; co-formulated BC30 trials ineligible; transit is a surrogate; resistant maltodextrin separated from resistant starch; 12 new study records (registry now 132 identities, 157 study records). Model rules: a primary outcome cannot be a subgroup; within-group, subgroup and ranking effects earn no primary credit; "strong" needs two positive trials of the same condition. MIMBb75 and Shirota trials not added (no catalog label) | `codex_audit_response_20260922.py` + `CODEX_AUDIT_RESPONSE_20260922.json` (per-finding disposition); `test_codex_audit_response_20260922.py` |
| 41 | Evidence review packet contradicted itself at zero pending ("decisions below have not been written") and miscounted `rejected_source` | Generator states the closed state, counts `rejected_source`, and documents the missing-direction invariant and where withdrawn citations are recorded | `test_evidence_review_packet_uses_frozen_fields_without_personal_metadata` |
| 42 | **The strain card claimed support for null evidence.** The app prints "`<level>` support · `<indication>`", and the level was the evidence strength alone: HN019 (null) shipped "High support · Functional constipation (primary … endpoint not improved)"; BB-12 (mixed/limited) would have read "High support" | `enrich_supplements_v3._derive_clinical_support_level` follows direction (positive keeps its level, mixed ≤ weak, null/negative/unresolved/missing empty); `_probiotic_indication_copy` shows no indication without qualifying reviewed evidence and states the result when the direction is not positive; `assessment_readiness` no longer reads the direction-blind registry `evidence_level` as support | shipped blob 205138; `test_every_strain_card_line_agrees_with_its_direction`, `test_a_reviewed_strain_without_supportive_evidence_is_evaluated_not_supported` |
| 43 | `evidence_level` drifted from the effective evidence strength on 14 identities | Data corrected; `db_integrity_sanity_check` error `evidence_level_disagrees_with_owner` | 14 findings on the pre-fix registry, 0 after; `test_evidence_level_is_the_effective_strength` |
| 44 | **21 interaction rules could never fire.** Rules written on a banned, botanical, additive or other-ingredient entry (CBD, ephedra, yohimbe, red yeast rice + statins, pennyroyal, tansy, rue, schisandra, hordenine/tyramine + MAOIs …) match only non-scorable rows, and the profile scanned scorable rows alone: CBD products shipped with no liver, seizure, pregnancy, lactation or drug-class warning | `_collect_interaction_profile` also scans label rows whose subject is a non-IQM entry; the 2026-06-24 policy that inactive / blend-child rows of scored ingredients raise no alert is unchanged | canary 246324 regains its 4 condition + 4 drug-class CBD warnings; interaction tests 285 pass; pre-run corpus: 55 products regain alerts (CBD 35, bitter orange 17, 7-keto DHEA 3) |
| 45 | One banned/high-risk hazard shipped as two cards: the resolver card lacked the `ban_context` its own reference carries, so the dedup key split | Resolver warning carries the reference `ban_context` | canaries 246324, 312711, 2219, 306181, 63921: one card per rule |
| 46 | **Seven test files read canary blobs frozen on 2026-04-22.** Their producer was deleted with the v3 scorer (`21148621`); `test.sh` pointed at the missing script, and the tests kept passing on April output | `scripts/reports/canary_rebuild.py` restored on the v4 scorer; canaries rebuilt; locks retargeted to their current owners with the reason; the v3 Section A lock retired (contradicts `test_blob_carries_no_v3_score_husks`); the E1.2.2 baseline rolled forward by its documented mechanism after each difference was classified | #44 was found this way |
| 47 | `studied_formulas` / `probiotic_evidence` read `indication_secondary`, which no entry has (the data field is `secondary_indications`): a read that could never be true, shipped as a null field | Dead read removed | no reader or fixture remains |
| 48 | **Four canary products had left the catalog** (GNC 1072, Nutricost 223318, Pure Encapsulations 182968, false-positive 184571). A canary the loader cannot find is skipped, so 11 slow-tier tests and their pins had gone unchecked | Re-pointed to the same brands' current SKUs, every value recomputed through the scorer; a low-band canary added; `test_every_canary_is_in_the_catalog` fails when a canary leaves the catalog | slow tier: 11 skips → 0 in those files |
| 49 | `test_canary_spring_valley_probiotic_50b_scoreable_at_p26` could never assert: its loop sat after `continue` inside the `except` handler, and the products root was one machine's absolute path | Loop restored, root resolved from the repo | the canary now scores 178346 |
| 50 | The omega canary coverage test required a canary at 20+/25 Formulation, which no product can reach since `45685529` moved disclosure to Transparency (the module declares `max_reachable_in_p161` 12.0; catalog max across 716 omega products is 12.0) | The bands derive from the module's own declared ceiling | `test_canary_set_covers_score_ranges` |
| 51 | Canary 76803's dose trait pinned the pre-`2026-09-16` reading (CFU guarantee not disclosed, ×0.85 → 3.4) although its label reads "Guaranteed potency through expiration date" | `regen_canary_pins.py` extended to regenerate trait pins; the guarantee state is now pinned explicitly per canary | slow tier; label text quoted in the pin |

## 3. Canonical owner matrix

| Domain | Fact | Canonical owner | Consumers | Duplicates found → resolution |
|---|---|---|---|---|
| Identity | ingredient identity, aliases, forms | `ingredient_quality_map.json` + Cleaner `_resolve_canonical_identity` | enricher, resolver, export | DPP-IV split (fixed); `bioflavonoids` vs `citrus_bioflavonoids` (generic class kept; citrus aliases route to citrus); chicory fiber IQM vs NHA (IQM wins for actives; one missing spelling added) |
| Row role | `cleaner_row_role` vocabulary | `constants.CLEANER_*_ROLES` | validator, scoring contract, taxonomy, audit, resolver | 4 copies → 1 |
| Formulation | form quality | scoring_v4 formulation modules | quality_score | none new |
| Dose | exposure / applicability | dose modules + `scoring_input_contract` | quality_score | `IQD_DOSE_EVIDENCE_CLASSES` 3 copies → 1 |
| Evidence | disposition → points | `evidence_resolver` → Evidence modules → `quality_score` | artifact, export, app | score>0 leak closed; literature registry = provenance only |
| Probiotic evidence | strain review state | `probiotic_measurements.context_review_finished` + `studied_formulas` | probiotic Evidence, confidence, component disposition | stale "pending" label fixed |
| Enzyme activity | activity units (SPU/HUT/…) | Cleaner `dose_class=enzyme_activity` | enricher, audit | no mg conversion anywhere |
| Transparency | disclosure / opacity | transparency module | quality_score | caps no longer double-count opacity |
| Verification | certification credit | verification module | quality_score | fail-open 6/15 is documented design |
| Safety | verdict / blocking / role scope | `gate_safety` + `identity/safety.py` | export (parity-asserted) | export was a second banned authority → fixed |
| Interactions | rule subject matching | `identity/interaction.py` | enricher profile, export tags | vitamin K family added; two keyspaces (profile ids vs catalog tags) are by design |
| Medication depletion | drug→nutrient depletion | `medication_depletions.json` (80 records, 0 duplicate pairs) | Flutter asset via `sync_flutter_reference_data.py` | 2 layer overlaps split/retired; Flutter asset stale → refreshed by release |
| Assessment state | complete / partial | `scored_artifact._quality_assessment_status` from Evidence display_state | export, app | now one-way from canonical Evidence state |
| Public score / tier | literal six-pillar sum, tier from shipped whole number | `quality_score.py` | export (`quality_score_v4_100`), app | cap removed; `score_100_equivalent`, `grade`, `display_100` kept as one-way external aliases |
| Banned / recalled detection | label name → ban entry | enricher `_check_banned_substances` (+ `InactiveIngredientResolver` for inactives) | Stage 3 gate, export (parity-asserted) | dead Cleaner detector `_check_banned_recalled` removed; its test intents re-pinned on the enricher |
| Probiotic strain identity | label strain ↔ registry strain | `studied_formulas.clinical_strain_identity_matches` | probiotic evidence, component disposition | dead enricher `_strain_match` removed; infantis-code test re-pinned on the owner |
| Other-ingredient reference | inactive/descriptor identity + flags | `InactiveIngredientResolver` | export blob, gates | `build_final_db` second lookup index removed |
| Dose safety (B7 over-UL) | typed UL flags → penalty | one `evaluate_dose_safety` call in `score_supplements_v4`, applied to every module | quality score, gate, export | 4 dead per-module B7 wrappers removed; parity tests re-pinned on the shared evaluation |
| Evidence efficacy relevance | is this canonical an efficacy active | Cleaner roles (`CLEANER_NON_EFFICACY_ROLES`) + `*_descriptor/*_marker` naming + Phase-4 literature disposition per canonical | Evidence universe, resolver | `is_label_descriptor` measured and rejected as owner (it is set on real dosed actives) |
| Blob top-level contract | which keys a detail blob may carry | `audit_contract_sync.BLOB_TOP_LEVEL` (strict snapshot gate) | D5.3 test, export tests | third drifting copy consolidated; undeclared keys now fail the gate |
| Evidence completeness (every route) | may a product be called complete | `evidence_resolver.resolve_product_evidence` → `generic_evidence.evidence_completeness_gap` | generic + probiotic Evidence, display state, assessment status | probiotic module decided completeness on its own branch order → now asks the one helper first |
| Probiotic strain review state | stub / sign-off / pending context | `studied_formulas.assess_probiotic_evidence` + `assess_probiotic_component_disposition` | resolver, probiotic Evidence | resolver treated the open state as terminal → fixed |
| Label text on projection rows | what the bottle says | label ledger `display_ingredients` + `identity_integrity.normalize_label_display` | `ingredients[].label_display_name`, `display_label` | identity step was a second source → ledger wins |
| Warning card identity | one hazard, one card | `build_final_db._warning_dedup_key` (rule id + condition + drug class + ban context) | blob warnings, app cards | spelling-keyed; flag-path card missing `ban_context` → fixed |
| Strain literature review state | reviewed-with-contexts / reviewed-no-qualifying / open | registry `literature_review` + `probiotic_measurements.strain_literature_review_concluded`; `studied_formulas.reviewed_strains_without_qualifying_evidence` | strain status, component disposition, resolver, probiotic Evidence, research presentation (app badge) | new; the entry's `evidence_level` / `notable_studies` now say the same thing |
| Strain human evidence | does approved human research exist | approved exact-strain contexts (`derived_context_evidence`); a signed human summary only where no approved context disagrees | probiotic Evidence, research presentation | `q3_human_clinical = NO` summaries were a second owner → D2 |
| Route of a hybrid label | multi vs probiotic | `scoring_input_contract._classify_route_module` (declared-multi title over a multi-eligible panel) | router (no fallback), scored artifact | D4 |
| Enzyme identity | which enzyme a label row names | IQM parent per enzyme, CUI-verified | Cleaner, resolver | 7 enzymes filed under `cellulase` → own parents (D8) |
| Depletion consumer copy | the clinical sentence on the card | `medication_depletions.json` reviewed `alert_body` | app `PGDepletionCard` (supply line only is client-side) | Dart templates were a second author → D6 |
| Blend-total members | which rows carry the dose | Cleaner `_lift_decomposition_members` at every nested-row loop | enricher, omega dose | a total with dosed members discarded them → §2 #33 |

## 3b. Stale tests (green, or skipped, but no longer testing the system)

| Test | What was wrong | Now |
|---|---|---|
| `test_pipeline_integrity` data-flow class | output glob matched nothing; skipped on every run for months | real path; moved to `test_pipeline_data_flow_artifacts.py` (artifact tier: loading the whole corpus overran the fast tier's 120 s) |
| 9 blob-reading test files | pointed at dead output paths → skipped | `release_artifact_paths.final_build_dir()/catalog_dist_dir()` (honours `PG_RELEASE_CANDIDATE_ROOT`) |
| blob samplers | first N files by name | evenly spaced across the catalog |
| Capsimax / canonical-id canaries | canary 1007 left the dataset; the test skipped silently | live canaries (176168, 213223, 213305; 1060); a missing canary now fails; blob check moved to the artifact contract |
| `test_rc4` | `xfail` guards around real invariants | plain asserts |
| fixtures with keys no artifact carries | `productName` (24 dicts in 10 files), `is_in_proprietary_blend`, `source_rule` (20), `isProprietaryBlend` | the live keys (`fullName`, `proprietaryBlend`, `source`) — key census over all five layers |
| `test_branded_identity_preserved` | read only the name line; the app renders a separate form line | reads both rendered lines: 206 rows keep the brand in the form line, 0 drop it |
| D2.7.1 (6 tests) | grepped enricher source text | one behavioral test on a real-shaped label (`test_d210_source_descriptor_child.py`) |
| D5.3 | a third drifting copy of the blob contract; never rejected an undeclared key | reads `BLOB_TOP_LEVEL`; undeclared key fails |
| probiotic species-copy test | fixture is under pending review, so it now pins the open-assessment copy | split: pending → "still open"; finished species research → species-level copy |
| 13 fast failures after the dead-code sweep | pinned dead features / dead keys | deleted with the feature or moved to the live key (report §2 #15) |
| slow tier (`scripts/test.sh slow`) | **51 failures, identical at `d70fd740` and on the round-1 code.** The tier is not in the dev loop, so it went stale unseen. D9 classified every one: 18 enzyme names + 1 B-420 = stale identity expectations (updated after 3 live alias regressions and the chemistry errors were fixed, §2 #31); 2 obsolete premises (algal DHA "source disclosed" is scored in Transparency since `45685529`; "SAFE above 40" predates `e26c9b98` and the fixture's certificate lacks verified provenance under `55dc2f46`) → retargeted; 1 **live defect** (259484, §2 #33) → fixed; 30 stale score pins from owner-committed calibrations (`45685529` omega one-pillar, `e26c9b98` POOR verdict, `55dc2f46` verification owner, the 09-13 → 09-15 rubric calibration) | 31 remain, all reading the on-disk enriched corpus: the 30 pins are re-frozen by `scripts/tests/regen_canary_pins.py` (recomputes each pin through the test's own call, prints the old → new ledger, `--write` edits only the numeric/verdict fields) on the final corpus after the run; the 259484 contract test passes once that corpus is re-enriched |

## 4. Duplicate-field audit (scored artifact → export)

| Field A (canonical) | Field B | Same value? | Both needed? | Action |
|---|---|---|---|---|
| `quality_score_status` | `scoring_status`, `scoring_metadata.scoring_status`, `_v4_quality_status` | yes | no | B removed |
| `quality_score_v4_100` | `_v4_quality_score_100` | yes | no | removed |
| `quality_score_v4_100` | `score_100_equivalent` | yes | external core column | kept, one-way |
| `quality_tier` | `_v4_quality_tier` | yes | no | removed |
| `quality_tier` | `grade` | yes | external core column | kept, one-way |
| `quality_pillars_v4` | `_v4_pillars` | yes | no | removed |
| `quality_score_confidence` | `_v4_confidence` | yes | no | removed (core `v4_confidence` alias kept: app fallback) |
| `route_decision`, `score_unavailable_reason`, `quality_score_suppressed_reason`, `raw_score_v4_100`, `dose_safety_evaluation`, `safety_signal_reason`, `safety_decision`, `safety_review_records`, `assessment_readiness` | `_v4_*` twins | yes | no | removed |
| `_v4_provenance.*_version` | `_v4_scoring_engine_version`, `_v4_classification_schema_version` | yes | no | removed; readers use provenance |
| `evidence_result_state` (science) | `display_state` (presentation) | no — one-way derived by `evidence_display_state` | yes | kept, distinct |
| `v4_verdict` (engine) / `verdict` (public) / `safety_verdict` (gate) | — | distinct | yes | kept, distinct |

## 5. Forensic lineage (Phase 0 → HEAD)

### 5.1 Eras audited against current code

| Era | Landmark commits | Current-code verdict | Proof |
|---|---|---|---|
| V3 → V4 cutover | `96dbb66a` Tradeoffs from V4 (2026-06-24), `f3bed2f2` one v4 artifact producer (07-16), `21148621` v3 /80 scorer retired (07-17), `f905af36` snapshots re-frozen | V4 is the only producer. **Residue found and removed this closure:** the scored-artifact `_v4_*` overlay + `scoring_status` (§4), and blob `section_breakdown` / `omega3_detail` / V3-derived `omega3_audit` and `proprietary_blend_audit` fields, which read a `breakdown` object V4 never emits and shipped 0/25, 0/30, 0/20, 0/5 and a zero omega-3 bonus / zero blend penalty for all 15,162 products; dashboard "Detailed Score Trace" rendered that V3 math. The 2.5.0 core columns `score_ingredient_quality*` etc. are NULL in every row and are part of the published 2.5.0 SQLite schema (schema 3 drops them): kept as an honest external contract. | dist census (15,162 blobs, all zero); `test_blob_carries_no_v3_score_husks` |
| Phase 0 calibration infra | `a1a863e8` config-driven registry | intact; tiers/magnitudes read from `quality_score.json` | tier boundaries verified in config |
| Phase 1a/1b row role + provenance | `b31c2ae4` | role vocabulary had drifted into 4 copies → one owner (§2 #10, #11) | `test_every_cleaner_role_literal_is_in_the_one_shared_vocabulary` |
| Phase 2 direction / materiality | `88a4bd41`, pairwise floors `6d633dee` | intact; pair count 134 → 133 only because the melatonin benefit statement left the safety layer (§2 #9) | `test_phase2_pairwise_classification.py` |
| Phase 3 clinical policy (Buff / peer lineage) | `196bbb69`, `82bedddc` EDTA, `7aaebb3e` folate, `9ae6efeb` decisions, sign-off Dr. Pham 2026-09-21 | intact; **one split-brain found**: export re-flagged inactive EDTA as banned (§2 #1) | Phase-3 policy tests 37 pass; 5 products export-parity |
| Phase 4 literature resolution | `1221c5a9` … `9be67755` | intact; literature registry is provenance only, never a scoring authority | `test_phase4_*`, live-verified PMIDs untouched |
| Phase 5 production integration | `039e1edc`, `d70fd740` | completeness leak (`total > 0 → evaluated_applicable`) closed (§2 #4); A/B-only switches removed after the final same-input A/B | §0 run results |
| Probiotic evidence (09-05 → 09-14) | `5f7dcfe9` 123 contexts approved | points intact; review-state label was stale (§2 #5) | NCFM 0 / LA-5 6 / LGG 8 unchanged |
| Vitamin K identity split | `e7a9e939` (2026-07-28) | **regression found**: 659 products lost the warfarin caution; fixed at the interaction subject owner (§2 #2) | 203346 fires both vitamin K rules |

### 5.2 Unreachable commits and archive tags (forensic only, nothing resurrected)

`git fsck --no-reflogs` → 129 unreachable commits: 47 patch-identical to main, 14 content-on-main, 25 empty/delete-only, 43 with unique blobs. The 43 are stashes/WIP snapshots, content later landed under other SHAs (direction ceiling ×3, form axis, IQM floors, Phase-3 source-resolution docs), or superseded designs. Every commit whose tests were missing from main was re-run against current code:

| Commit | Content | Verdict |
|---|---|---|
| `a4f2f8741` | competing cloud-branch lineage fix | SUPERSEDED by `primary_mass_competitor_rows` (one lineage owner) |
| `07fe77e30` | astragalus join | SUPERSEDED by the reviewed join (`test_botanical_lost_match_dispositions`) |
| `02f4686f3` | old display-ledger shape | SUPERSEDED by the label-ledger rework |
| `db0f35836` | "K1 and K2 must share an interaction group" | **REAL REGRESSION on main → fixed** (§2 #2) |

| Archive tag | Remote before | Content vs main | Verdict |
|---|---|---|---|
| `archive/phase5_frozen_wip_703ea0d3` | yes | 7/8 files identical to main; the 8th (`run_phase5_production_ab.py`) was later rewritten by `d70fd740` | SUPERSEDED |
| `archive/pre_phase5_reconciliation_5154a2ce` | yes | pre-reconciliation twin of `039e1edc`; its 5 differing files were all rewritten by `d70fd740` | SUPERSEDED |
| `archive/claude-probiotic-evidence-audit-2026-09-08` | yes | `7c8b5fa0` carries the same fix; test on main | SUPERSEDED |
| `archive/timing-rules-v6-2026-08-01` | yes | timing schema 6.0.0 on main and evolved since (`09767e05`, `980504c3`) | SUPERSEDED |
| `archive/solo-submission-20260913` | **local only** | content on main under other SHAs | SUPERSEDED; tag pushed so the evidence survives this machine |


## 6. Historical open-note closure matrix

Every historical TODO / OPEN note found in the repo docs, audit folders and the
project memory for this workstream, with its end state. Allowed end states are
CLOSED, OBSOLETE / SUPERSEDED, or IRREDUCIBLE SOURCE LIMITATION. Items that need
an owner decision are listed in §7, not here.

| Note (source) | End state | Proof |
|---|---|---|
| Phase-3 E2 source resolution ×6 | CLOSED | `196bbb69`, replay evidence `de260e3c` |
| Phase-3 EDTA 8+8 policy | CLOSED | `82bedddc`; export split-brain fixed this closure (§2 #1) |
| Phase-3 folate 201420 residual | CLOSED | `7aaebb3e` |
| Phase-3 pharmacist sign-off | CLOSED | recorded Dr. Pham / Clinical Team, 2026-09-21 (`9ae6efeb`) |
| Vitamin-A gap (Phase 3) | CLOSED | policy decision recorded in the Phase-3 decisions doc |
| Peer enzyme schema failures | OBSOLETE | enzyme clinical audit 0 findings on the fresh corpus |
| Discrete enzyme form verdict | CLOSED | `NOT_INDIVIDUALLY_RATED`; activity units never converted to mg |
| D-ribose, green coffee, white willow, L-serine | CLOSED | terminal in Phase 4 (`9be67755`) |
| Null-direction evidence multiplier | CLOSED | `79f14633` (null earns 0.0) |
| Evidence-expansion pending contexts | CLOSED | `5f7dcfe9` approved 123 contexts; the stale "pending" label fixed this closure (§2 #5) |
| Rename `standardization_marker` | OBSOLETE (declined) | cosmetic; one owner already (`constants.CLEANER_*_ROLES`) |
| Rename omission reason `duplicate_source_line` | OBSOLETE (declined) | cosmetic |
| `needs_info` 12300 / 75291 / 254396 / 254413 | 75291 CLOSED (ratified). 12300 / 254396 / 254413 IRREDUCIBLE SOURCE LIMITATION: the DSLD record does not carry what the active needs (`source_active_assessment_required`), so they are `not_scored` / `blocked_by_completeness_gate` and quarantined — never shipped with a score; remedy is a reviewed label correction through the submission lane | C1 scored artifacts; Phase-3 integration report §4 |
| V3 retirement handoff Track A (V4 tradeoffs) | CLOSED | `derive_v4_tradeoffs` (`96dbb66a`) |
| V3 handoff Track B (dead V3 blob surfaces) | CLOSED this closure | `section_breakdown`, `omega3_detail`, V3-derived audit fields, duplicate `audit.*`, dashboard V3 score trace removed; `test_blob_carries_no_v3_score_husks` |
| V3 handoff Track C (stop computing V3 shadow) | CLOSED | `21148621` retired the /80 scorer; `shadow_diff_snapshots.py` deleted this closure |
| V3 handoff Track D (duplicate blend grouping, 336897) | CLOSED | post-merge header/body consolidation in `_merge_blend_evidence` |
| V3 handoff Track E (test alignment) | CLOSED | V3 fixture shapes removed from the export tests this closure |
| V4 pass-2 memo: Flutter ranker reads V3 `score_brand_trust` | OBSOLETE | the app no longer references any V3 section column; the 2.5.0 columns ship NULL (schema 3 drops them) |
| V4 pass-2 memo: export gate requires V3 `section_scores` | CLOSED | gate no longer reads `section_scores`; the last dead read replaced by explicit NULLs |
| Supp-type consolidation Phase 5 step 5 (delete retired scorer) | CLOSED | `score_supplements.py` gone (`21148621`) |
| Supp-type consolidation Phase 5 step 7 (temporary harness, `percentile_categories.json`) | CLOSED this closure | harness + 2 tests deleted; config retired (loaded, never read) |
| Silent-empty-fields memo: GMP two owners | CLOSED | Verification owns GMP; `certification_detail.gmp.audited_facility` copied from the pillar |
| Silent-empty-fields memo: evidence card tier computed in Flutter | CLOSED | app card headline reads the Evidence pillar (app `5406845`) |
| Silent-empty-fields memo: `omega3_detail` empty | CLOSED this closure | blob block and the scorer fallback that read it removed |
| Catalog memo: "strengths" could list a safety concern | CLOSED | `_build_v4_score_explanation` only lists full-credit pillars as strengths |
| Evidence-batch memo: probiotic `max(generic, native)` credit | CLOSED | credit ownership is emitted (`credit_owner`, `strain_points`, `companion_points`) and the copy never calls companion evidence strain research |


## 6b. Residual partial products (measured on the round-2 code; confirmed in §0 after the final run)

Round-2 full chain, all 15,414 labels: **56 shipped partials, down from 118 at C1**; after Dr Pham's
2026-09-22 review closed F1 (§2 #37), **1**.

| Products | Held by | End state |
|---|---|---|
| 37 | Bi-07: clinician sign-off suspended 2026-09-04 after a citation-identity mismatch | CLOSED: Dr Pham restored the sign-off (§2 #37); reviewed, surrogate-only, no efficacy credit |
| 16 | BB-12: same suspension, plus the two LA-5/BB-12 combination contexts the owner held `adjudication_required` on 09-14 | CLOSED: sign-off restored (null primary outcomes); both contexts approved as literal combination records |
| 2 | only those two held contexts (LA-5 products without BB-12): 30439760 (three-strain LC-01 yogurt) and 39102225 (PRIMAL; an unnamed B. infantis) | CLOSED: approved with their unregistered third strain recorded (`unregistered_components_present`) |
| 307560 Bile Acid Factors (Jarrow) | DSLD nests "Total Bile Acids 1000 mg" as the **parent** of "Bovine Bile concentrate 1630 mg" (an assay total cannot contain a heavier material); the only such inversion in 15,414 raw labels. The literature records call both bile-acid rows analytical specifications, and the resolver fails closed on them | IRREDUCIBLE SOURCE LIMITATION — remedy is a reviewed label correction through the submission lane (keeps the DSLD id), not a one-product rule |
| 307569, 81801, and the five "Bulgarian Yogurt Concentrate" labels | were identity decisions (D3) | CLOSED by §2 #32 |

## 7. Decisions D1–D9 (resolved 2026-09-22) and fork F1 (closed by Dr Pham, 2026-09-22)

Round 1 listed D1–D9 as forks. Codex's review (relayed and endorsed by Sean on
2026-09-22) said each was resolvable from established doctrine; all nine are now
resolved at their owner. The one clinician hold, F1, was sent to Dr Pham on a review
sheet (https://claude.ai/artifact/3Bhz3oj3qgLBsYZz3iwiof) and closed by her the same day (§2 #37–#39).

| # | Question | Resolution | Where |
|---|---|---|---|
| D1 | Registry strain stubs never reviewed | Literature-reviewed to a terminal state in one bounded batch: 15 strains with single-strain controlled trials recorded as contexts, 74 no qualifying human evidence with reasons, 0 stubs left. Bi-07 / BB-12 excluded (F1) | §2 #25, #26, #28 |
| D2 | Approved human contexts vs a summary's `q3 = NO` | One owner: approved human contexts own human evidence; research presence earns nothing without a positive primary patient-important outcome | §2 #27 |
| D3 | 307569, 81801, yogurt concentrate identity | Source-aware citrus bioflavonoids; PMF parent; the concentrate is a dairy food | §2 #32 |
| D4 | Multi + probiotic hybrids | Dominant declared identity routes; strains keep probiotic-owned disposition; no score blending | §2 #30 |
| D5 | Dose-aware Evidence | No: dose is only an applicability gate (0 credit), the multiplier is gone | §2 #29 |
| D6 | App depletion copy | The reviewed `alert_body` is the card's clinical sentence | §2 #35 |
| D7 | 12 unread blob sections | Kept in 2.5.0, deprecated for schema 3, pinned unread | §2 #36 |
| D8 | Enzymes under the wrong parent | Seven enzymes on their own CUI-verified parents; three dropped aliases restored | §2 #31 |
| D9 | 51 slow failures | 19 identity pins updated, 2 obsolete premises retargeted, 1 live defect fixed; 30 score pins re-freeze through `regen_canary_pins.py` on the final corpus | §3b, §2 #33 |

### F1 — closed by Dr Pham on 2026-09-22 (the hold as it stood; she reviewed both and chose option A on the sheet for 1a, 1b and 1c)

| Hold | Facts | Options |
|---|---|---|
| Bi-07 and BB-12 clinician sign-offs, suspended 2026-09-04 after citation-identity mismatches ("replacements require clinician review") | Each strain has approved exact-strain human contexts (engineering-owner approval, 09-14). The code rule `identity_review_accepted` keeps a suspended sign-off under the clinician gate: an engineering approval is not its clinician replacement. 37 products (Bi-07) + 16 (BB-12) | (a) keep the hold until Dr Pham reviews (today); (b) let the approved contexts replace the suspended summaries, as D1 did for agent-authored summaries |
| Two LA-5 combination contexts held `adjudication_required` on 09-14 | 30439760 needs LC-01 registered; 39102225's third component is an unnamed B. infantis that no identity can register. Combination contexts never credit a strain; approval only finishes the review. 16 products share this with BB-12, 2 are held by it alone | (a) keep holding; (b) approve both as combination records with `component_registration_status: unregistered_components_present` |

## 8. Field census (every layer, real corpus)

Tool: `scripts/audits/closure_20260921/field_census.py` (present / populated
counts per field, static writers and readers, dashboard and app consumers —
quoted keys, plus bare words for core columns read in SQL). Hard failure: an
undeclared detail-blob top-level key → **0**. Every flagged field has an end state:

| Class | Fields | End state |
|---|---|---|
| Deprecated compatibility, empty by contract | core V3 `score_*` (8, NULL); core + scored `badges` (always `[]`, app no longer renders badges); `warnings[].dose_threshold_evaluation` (NULL; superseded by `dose_decision`, which the app reads first); core `thumbnail_key`, `image_thumbnail_url` (resolved at runtime by the app from the storage path) | Documented; nothing fabricated; schema 3 drops |
| Source limitation | `discontinued_date` / `discontinuedDate` (every staged label is `offMarket = 0`, no discontinuation events); cleaned `images` (not in staged DSLD); `updatedDate` (not in staged DSLD; live passthrough for submitted/manual labels via `label_record_contract`) | Kept as source passthrough |
| Fail-safe diagnostics, empty = healthy | enriched `unmatched_ingredients/_additives/_allergens/_delivery_systems`, `rejected_claim_matches`; scored `scoring_fallbacks_used`; blob `product_status(_detail)` (nullable) | Kept (`rejected_manufacturer_matches` from the same ledger fills on 487 products, so the path works) |
| Provenance / audit metadata | `enriched_date`, `enrichment_metadata`, `reference_versions`, `compatible_scoring_versions`, `manufacturer_normalized`, `evaluation_stage`, `safety_review_records`, cleaned `upcValid`, inactive `label_row_disposition` / `resolved_display_label`, `harmful_notes`, `warnings[].ingredient_role` | Kept as audit trail |
| Emitted, unconsumed shipped payload | 12 blob sections + core `brand_family` / `brand_name_raw` | Deprecated for schema 3 (D7, §2 #36); pinned unread |
| Removed this closure | enriched `percentile_category_label/_source/_confidence/_signals`; the field reads in `REMOVALS_AND_RETENTIONS_20260921.md` | FIELD proof |

Retained external aliases (owner → one-way alias → consumer), every removed
function with its proof category, and every "looked dead, is live" guard are in
`REMOVALS_AND_RETENTIONS_20260921.md`.

