# PharmaGuide product roadmap

October 30 Dose/Cascara release batch: exact-scope approvals and the eight-product held-assessment publication disposition are integrated in pipeline main `2c8e05a68` via PR #299. All four final fast CI shards and merge readiness passed on combined source `ca9b7bfb8` (run `41001000762`); named owner, consumer and Flutter blob checks passed. The 164 frozen original labels show the intended Dose movements and 19 public NOT_SCORED transitions (11 R. davurica plus eight newly approved held labels), with no product-safety-status movement. Submission batch PR #300 is also integrated in main `c81e0a1f6` after exact CI run `41003477994`. Sean's one final Clean→Enrich→Score run, fresh corpus/release gates, checksum catalog and installed-app acceptance remain open. The existing pending-items LEDGER records the bounds and receipts. No release or beta box is checked from source-only evidence.

October27 returned-review follow-up integrated: runtime8a0327aa0, CI40572399333all4shards/skipguards/Merge readiness green, PR265merge415746189.1284targetedpass;local546/24declaredskips+guard;36labelsbefore/after8newcomplete/0lostcomplete/0identity-amount-safetychange;17backedsubjects+BC30nativeownerreconciled. All317C/Dreceived; source24complete/122incomplete across146usedfrozenIDs,352preparationworkgroups—notmissingsignatures. Original20diagnostic7complete/13blocked; corpus/app/100kscale remainunqualified. No pipeline or publication. See current qualification report/registers.

October23 MCP usability deployed: existing catalog search prefers full-text matches before fuzzy fallback; shared disabled-personal copy and canonical connection guide are live. PR243pipeline/134app merged with approval. Both exact-source CIs passed (pipeline40008017706/app40008166478); production15HTTP checks and6actualCodex calls passed. Details and migration/function versions are in the existing LEDGER. ClaudeCode testing deferred by Sean due token exhaustion; personal access stays disabled. No catalog rebuild or clinical changes in this batch.

October23 release performance batch is implemented and independently reviewed on `codex/release-performance`: bounded upload queues,
content-bound interaction reuse, and release failure protections; no clinical/public contract change or release.
334 named checks and exact-candidate CI39972973617 pass; component scaling benchmarks are tracked in the existing pending-items LEDGER.
This does not complete catalog/app release acceptance.

Written October 1, 2026 from the business strategists' review (pipeline, app and market
recommendations), checked against the three repositories and the live market. Sean approved the
order below on October 1.

October 13: the supported warning/context corrections are implemented, measured, independently reviewed and validation-complete. Seven source records changed. The schema-4 export and app consumer now evaluate confirmed forms, actual daily amounts and current food/procedure context. All 24 native data comparisons and three frozen raw replays pass, with no product-quality movement.

Pipeline source `4b74d1b1` passed CI run `38377932566`: 20,559 tests and 192 declared skips, with every skip guard passing. The 174 focused tests and local 546 tests also pass; local has 24 declared opt-in skips. App source `545c4138` passed CI run `38378191655`; its local check passes clean analysis and 3,885 tests. PR134 merged at `e4c944a15f8c533fcb1a101db3892704a40d02d9`; app PR113 merged at `fdd5ca054b4c41927336c123f98302dc00b3dfb2` on October 13. Both approved heads are ancestors of origin/main. Exact-head pipeline CI38382804581/38382810605 and app CI38380987827 passed. Both merged local and remote branches were deleted after containment verification. No catalog rebuild, bundle/pin replacement, visual acceptance or release occurred. The full catalog, paired artifacts, visual acceptance and release remain deferred. Clinical preparation, form and source holds remain documented in the existing LEDGER, research and private FOLLOWUP_20261013.md.

October 13 AI connector audit: containment is merged and deployed (pipeline PR136/main934e8027e, app PR114/main14152b88, website PR5/main82c761d). Both forward migrations and all three Edge functions are deployed; personal reads and snapshot uploads return503, authenticated deletion remains available, and production DCR is disabled. Exact-source CI passed: pipeline dd5341b4/run38437257217, app015a43fe/run38441160359, website47acd1f/run38436761594. Website PR6/main56bfefe adds the verified public hostname https://mcp.pharmaguide.io/public; exact-source CI38467026860 and live known/missing barcode probes passed. Codex discovers the three public tools. Public comparison/serving PR138 and app116 are merged with exact-source CI green (pipeline38480745011/app38480579994). Shared serving correction was measured on552rawlabels; publication still requires a full catalog rebuild. Follow-up assessment-context runtime4d29ce76/app80a45e9e corrects source-backed parent disclosure (CitraMate80→86), projects canonical dose/reference/penalty context, preserves all form labels, and formalizes public scope/ranking.1510stored parent products:341Transparency-only score changes,zero safety/status/route changes; final six-call Codex fixture acceptance and independent review passed. Exact runtime CI38489047181/app38487682633,local546,raw33canaries and appreaders71 passed; appPR117 merged main114787cd. Sean will run the required fullClean→Enrich→Score pipeline-only himself after pipelinePR139 merges. Final corpus/catalog/app release gates remain pending. The first corpus run was stopped during the first brand for this additional source work; no public comparison deployment is claimed. Personal OAuth remains contained independently of the public release. WorkOS confirmed manual-client resource binding is not enforced and no immutable authorization/family ID is exposed; the requested staging client IDs were sent privately with Sean's explicit approval. DCR/CIMD needs staging qualification. See the existing LEDGER for exact evidence and remaining gates.

October22 zero-pillar source audit is integrated in main2a04ad859 (runtime19755342c): all5,512 saved-zero products classified, verified source defects fixed,1,044 unique affected/control labels measured and independently reviewed. Final exact-source CI39894910595/local/raw-canary gates pass. This closes the source audit, not producer/catalog/app acceptance;10 honest quality holds remain; the October23 follow-up fixes213846 export provenance (final integration receipt in LEDGER). [Report and per-product results](../../scripts/audits/zero_pillars_20261022/README.md); existing LEDGER retains receipts.

How this document relates to the others:

- [Master completion plan](PHARMAGUIDE_MASTER_COMPLETION_PLAN.md) is **Phase 0** here: the scoring
  remediation in progress. Nothing in this roadmap changes it.
- [LEDGER.md](../../scripts/audits/pending_items_20260926/LEDGER.md) stays the one execution
  register. Rows S1.1–S6 there point at the items below; close an item in the ledger, then tick it here.
- The [ownership matrix](../../scripts/contracts/source_of_truth_matrix.json) and `docs/adr/` decide
  owners. A new exported field, status or policy named below still needs Sean and an ADR.

Paths: bare paths are this repository; `app:` is `/Users/seancheick/PharmaGuide ai`; `web:` is
`/Users/seancheick/PharmaGuide Website`. Evidence marks: **[V]** verified in code on October 1;
**[A]** reported by a read-only survey that day, so re-verify when the item starts. Current code
outranks this document.

## Position

The scanner brings people in; the engine is the product. Scan + score + AI chat is now a commodity
(SuppCo, Prove It, Suppi, NutriStack, StackIQ all claim it). What others cannot copy quickly is the
governed data underneath: exact identity, form and dose, the interaction rules with their gates,
the citation checks and the replay corpus. The next stage is therefore not more backend. It is
showing what the backend already knows, then **Stack Impact**, then **Change Watch**.

Every result answers three separate questions, never merged into one number:

| Layer | Question | Owner |
|---|---|---|
| Personal Fit | Can I use this? | Rules written by the pipeline, applied on the phone to the local profile and stack |
| PG Score | Is this a good product? | Pipeline, six pillars, the same for every user |
| Analysis Coverage | How complete is this analysis? | Pipeline (to be exported as one value, item 1.3) |

A critical product safety gate (recall, ban, adulteration) sits above all three: BLOCKED, no score.

October 12 pairwise-source candidate: all 52 hard warnings and 16 dose floors reviewed (plus acetaminophen/warfarin). Fifty pair corrections and approved EPO pair removal implemented;15 unsupported floors removed, one niacin qualifier retained with form hold. Native131-row build and54 actual Flutter before/after probes pass;506 focused owner tests and independent surgical review pass. Exact-source8ba68dbe whole-fast CI38314549265 passes20,455tests/192declared skips; local546passed/24declared opt-in skips, guards green. No catalog run or delivery claim. MAOI-ginseng/kava-acetaminophen hard grades, niacin form eligibility and pairwise context remain open. Details: `scripts/audits/pending_items_20260926/research.md` / `LEDGER.md`.

## Decisions already made

| Date | Decision |
|---|---|
| 2026-10-01 | Personal Fit stays on the phone. The pipeline writes the rules; the phone applies them. The profile never leaves the device for this. |
| 2026-10-01 | One compact personal card: a safety line always; a goal line only when the product matches a goal or works against one; nothing when neutral. |
| 2026-10-10 | Superseding the 2026-10-01 order ("first external beta after Stack Impact"): a small invited TestFlight beta once the core flows work reliably (Launch track L7); full Stack Impact is built alongside tester feedback. Social builds awareness now, with wording that states availability accurately. Forwarded by Sean. |
| 2026-10-10 | Clinical verification model (Sean): Laurie Pham, PharmD has reviewed the clinical content and stays on the team; the "reviewed by a licensed pharmacist" and "Clinician-reviewed" claims stay. From now on the agents do the checking themselves (Launch track L4) and do not route routine work back to her. |
| 2026-10-01 | Business team's answers to the decision queue, forwarded by Sean; see "Decisions taken" below. |
| 2026-10-01 | Public catalog wording: the catalog is "sourced from NIH's Dietary Supplement Label Database (200,000+ labels)". No product count is shown (Sean: 15k reads as weak; 180,000+ described neither our catalog nor the source). |
| 2026-07-23 | No consumer change timeline or notifications before beta data shows the changes are meaningful (signal-lifecycle guardrail). Still in force: Change Watch UI is Phase 4. |
| 2026-07-22 | No user-facing health score for the stack; use status and concern counts. |

## Launch track — October 10, 2026

North star (Sean, sharpened October 11): **anyone who scans a supplement gets a straight, verified answer: what the product is, whether it is good quality, and whether it is safe for them (their pregnancy or breastfeeding, conditions and medications), with the reason and the source. We flag only real, sourced concerns, never noise; when we find none we say "no known concerns", never "safe". No invented claims, and never a false reassurance.** Example: a pregnant user scans a St. John's wort product and is told at the top of the page that it is not for her during pregnancy, why, and the source. It heads AGENTS.md in all three
repos. "Never a false reassurance" is the design standard for every verdict and all-clear; it is not
a marketing guarantee and never appears as one. Sean wants the product launched soon with a steady
blog cadence; this section orders what is left. The phases below keep their detail; the ledger rows
S1.x stay the register. Revised the same day after an outside planning review; each point was
checked against this document and `_public_verdict` before adoption.

Status checked October 21 against the candidate and completed corpus: Phase 0 remains complete.
The pre-beta candidate removes the low-coverage verdict override, mounts the existing Analysis
Coverage section beside the pipeline-owned result, deletes the unused numeric FitScore arithmetic,
and adds real-product safety/stack/nutrient acceptance cases. It also restores source-backed,
target-specific reasons for currently emitted actionable pregnancy and breastfeeding warnings.
Bounded measurement and local behavioral/app validation are complete; exact-head CI, independent review, integration, Sean's necessary
rebuild, rebuilt-catalog parity and Flutter release acceptance remain open. Items 1.6, 1.7 and 1.9
have not started; 1.8 keeps the citation debt; 1.10 still has focused subsets only.

### Before public launch (trust-critical)

| # | Item | Why it blocks launch | Builder → reviewer | Sean decides |
|---|---|---|---|---|
| L1 | North star in all three AGENTS.md files | Agents act toward a goal only if it is written | Claude (done October 10, branches `claude/north-star*`) | Approved October 10 |
| L2 | 1.3: coverage out of the verdict, with one exported Analysis Coverage value, **shipped together with the app showing it** | **Candidate measured October 21:** the pipeline no longer turns low-coverage SAFE into CAUTION; Flutter retains the pipeline result and mounts the existing `mapped_coverage` section directly below it. No new export field or second calculator. Ten frozen products preserve score/status/tier/safety/ingredients/allergens; pipeline local passed 546/24 declared skips and app `make check` passed analysis/3,962 tests. Exact-head CI, independent review, integration, rebuilt-catalog and Flutter release acceptance remain. | Codex pipeline + app → fresh-context review | Existing owner contract; no new policy |
| L3 | 1.10: gold benchmark in the release rung, judged by coverage, not count | Each required class has meaningful cases: severe interactions and contraindications, missing or hidden amounts, aliases and branded forms, unit/amount resolution, recalls/bans, and pipeline↔app parity. Expected answers are set from the rule's source and checked by someone other than the author. 300–500 is an estimate of what that coverage takes, not the gate | Codex authors, extending the existing fixtures → Claude checks each expected answer against the source; Laurie spot-checks severities | None (scenarios follow existing rules) |
| L4 | Clinical verification by the agents (Sean, 2026-10-10) | Every clinical claim is checked live against the APIs (PubMed, PubChem, GSRS, UMLS, openFDA): the study's title and body must be the right study, and its ingredient, population, dose, outcome and severity must support the claim; a resolving ID is not enough. A second agent reviews each change and tests what the app displays. Laurie double-checks when convenient; nothing waits on her | Claude verifies → Codex reviews and checks the app | Anything the sources leave genuinely unresolved |
| L5 | 1.8 citation gate: close material citation defects in shipped records | A citation that resolves does not prove the claim. Records in the 252-item baseline debt that ship in the beta catalog are fixed or withheld first; the rest stay in the Q22 burn-down | Claude triages the debt by shipped/not shipped and materiality via `/data-fix` → Codex re-verifies | Withholding a record |
| L6 | Claims parity across website, social and app | One claim set: the June how-it-works carousel says "180k+" (decision 2026-10-01: no product count, "sourced from NIH's DSLD, 200,000+ labels"); "Private, on your device" must match the privacy decision ("Core Personal Fit and stack safety logic runs on your device") | Claude lists mismatches → Sean edits social | Final wording |
| L7 | Invited TestFlight beta (decided 2026-10-10) | Opens once this week's order below passes on the finished candidate: existing stack checks working, their limits stated in the app, no claim of full stack analysis | Integrator validates the candidate; Sean invites testers | Who is invited and when |
| L8 | Personal verdict at the top of the product page (north star, October 11) | A pregnant, breastfeeding or condition-flagged user must see, before anything else, whether this product is for them, why, and the source; an ingredient with no pregnancy data must say so, never read as safe. Status checked October 11 on real exports: the data path works (GNC St. John's Wort 18219 exports "Birth-defect signal — avoid in pregnancy" with NIH/NCCIH sources; 152 rules carry pregnancy/lactation gates). Profile: Pregnancy, Breastfeeding and Trying to Conceive are separate selectable conditions (app taxonomy → flags `pregnant`/`breastfeeding`/`trying_to_conceive`). Real-code probe October 11 (production `composeGuardedWarnings` → `partitionProfileWarnings` → `buildProfileRelevanceSummary` on real exported blobs): pregnant + St. John's Wort 18219 → "Not recommended for your profile" with the avoid row (correct). Defects: (a) breastfeeding text — `enrich_supplements_v3.py` builds both the pregnancy and the lactation row from one `alert_headline`/`alert_body`, so a breastfeeding user on 18219 reads "Not recommended during pregnancy… If you are pregnant…"; 22 rules rate both but carry pregnancy-only text, 2 the reverse (`RULE_IQM_VITAMIN_B6_LACTATION`; `RULE_IQM_SAGE_LACTATION`, where a pregnant user gets "avoid" with only milk-supply text, so the pregnancy reason is missing); (b) both rows copy one shared profile gate (`pregnant` OR `breastfeeding`), so a pregnant user also sees the lactation row as a duplicate; (c) silent all-clear — `no_data` rows are exported (17,658 pregnancy, 18,610 lactation, copy "Limited safety data") but the app deliberately drops them (`warnings_pipeline.dart`, test-locked "if we don't know, we don't flag"), so a pregnant or breastfeeding user scanning Carnitine 500 (33684) or Enhanced Krill Plus Omega 3s (302654) gets a green "No concerns found"; 413 products have only `no_data` pregnancy rows and no other warning. **Sean's decisions (October 11):** (1) Missing data is not a warning: `no_data` rows stay out of the warning list, because flagging every unknown is noise that makes the app useless; show only real, sourced interactions. (2) The all-clear headline changes from "No concerns found" to "No known concerns" (we found none, not "there are none"), with one small line underneath for pregnancy/breastfeeding profiles pointing to their obstetrician; no "limited data" wording, which reads as unfinished. (3) Where one warning truly applies to both pregnancy and breastfeeding, one shared text is right: rewrite the 24 affected rules' existing `alert_headline`/`alert_body` so each reads correctly for both life stages (and gives sage its pregnancy reason), each verified against its source via `/data-fix`; no new schema field. (4) Remove the duplicate row a pregnant user sees (shared gate). App headline + footnote **done October 11** (app main `d9fbc861`: fail-first tests, 86 owner/consumer tests pass, analyzer clean, real-blob probe: Carnitine 500 + pregnancy → "No known concerns" + obstetrician line; St. John's Wort + pregnancy stays "Not recommended"; app CI run 38181615176 green on that exact commit). Pipeline half **verified October 21 on the released catalog 2026.10.21.140823**: all 54,016 breastfeeding rows carry breastfeeding wording (0 pregnancy-worded), 0 pregnancy rows are breastfeeding-only, and the St. John's Wort pregnancy row is gated to `pregnant` alone. Candidate October 21 closes the remaining source defect and adds the real-blob cases: explicit target rules override shared fallback, every currently emitted actionable life-stage rule/target projects a reason and source, and the app cases cover St. John’s wort, sage, magnesium/kidney, calcium/levothyroxine, no-data and a control. CI/review/integration/rebuilt-artifact acceptance remain. Previously listed: pipeline copy and gate after Codex's clinical-registry lane lands, since it is editing `enrich_supplements_v3.py`. Absorbs item 1.5 (personal card) into the pre-launch set | Claude builds the end-to-end gold cases and the app check → Codex reviews; breastfeeding wording via `/data-fix` after Codex's clinical-registry lane lands | Breastfeeding-specific alert text as a rule field (schema change) |

### This week (October 10–17), in order

Bounded to these six; it is not a promise to clear the historical backlog. Every remaining item
leaves the week with a disposition (done, held with reason, or scheduled) and its evidence, so
nothing quietly disappears.

1. **L8: the personal verdict, end to end.** App: "No known concerns" headline plus the small
   obstetrician line for pregnancy/breastfeeding profiles. Pipeline (after the clinical-registry
   lane lands): shared pregnancy/breastfeeding text corrected for 24 rules, duplicate row removed.
   Real-blob gold cases from profile to visible card: pregnant + St. John's wort, breastfeeding +
   St. John's wort, pregnant + sage, kidney disease + magnesium, levothyroxine + calcium, a
   `no_data`-only product (expects "No known concerns", no warning), and an unaffected control.
   Existing tests are checked against source before being trusted; stale ones are corrected.
2. **Verify depletion, stack interactions and nutrient accumulation end to end**: units, serving
   quantities, duplicate ingredients, missing amounts, applicable upper limits, and medication/profile
   triggers, checked on real products through to what the app shows.
3. **L2: ship coverage and safety presentation together.** A poorly assessed product never gains an
   unqualified all-clear.
4. **Remove the unused FitScore arithmetic** (`scoreFit20`, `e2cPenalty`, `maxPossible`) after the
   dead-code proof. Keep personal relevance, medication warnings and goal context; behavior matters
   more than the name.
5. **Close known defects and validate the finished candidate**: representative real products and
   phone checks, before the build goes to invited testers (L7).
6. **Content alongside**: magnesium, melatonin, label reading and certification seals, each paired
   with a social post using the same verified facts.

October12 independent candidate audit for items2/5: production-reader and provider checks
cover interactions, depletion, cumulative nutrients/units, profile gates and incomplete data.
The active catalog and all69blocked products were checked; signed build21 repairs one broken
DailyMed citation through the existing pipeline interaction owner. Tests also expose and repair
stale canary expectations for previously integrated green-tea standardization; no clinical policy
or app decision engine was added. Evidence: `/Users/seancheick/pg_quality/build20_independent_audit_20261012/REPORT.md`.
Whole-registry clearance and physical-device acceptance are separate; existing holds remain.
Final automated checkpoint and integration status are recorded in the LEDGER/report.

### During beta

1.4 page order (needs L2), 1.6 "Why this score"
(export contract: Sean), 1.7 rule typing, 1.9 export versioning, the rest of 1.8 (Q22 burn-down,
then the broad citation scan as a full gate), then Phase 2 Stack Impact.

### Content (runs beside everything)

A target of two blog posts a week (not a promise) from the ranked backlog
`web:docs/13-blog-topic-backlog.md`, each through `/pg-trends` (what people ask and share, new research and recalls; demand, never facts) then `/pg-blog-mdx`, verified under the L4 model; `pnpm blog:validate` checks every PubMed/DOI citation live. Start with
magnesium, then melatonin, to match the social series. Sean runs social media outside these repos and
pairs each post with a carousel. Posts the blog gate marks risk 31–70 (`web:pnpm blog:publish-check`
needs a `reviewer:` field) go to Laurie in a batch for a quick double-check rather than one at a time.

### Roster

| Who | Owns |
|---|---|
| Sean | North star, policy and clinical decisions, pushes to main, releases, social media |
| Laurie Pham, PharmD | Clinical reviewer on the team; double-checks agent-verified work when convenient, without back-and-forth |
| Claude | Building in one worktree per batch; blog drafts; integration when Sean names it the integrator |
| Codex | Fresh-context review of Claude's behavioral diffs (and Claude of Codex's); benchmark authoring |

Autonomy grows by change class (AGENTS.md validation table): documentation and tests-only batches
are merge-ready after their checks; behavioral batches also need the fresh-context review and green
CI. Pushes to main stay Sean's.

## Phases

### Phase 0 — finish the current remediation

October 13 magnesium checkpoint: combined Option C calibration, Purefruit owner correction and preparation/source identity fixes are implemented and measured on289 frozen labels. Eight exact-preparation assessment holds are intentional; glycerophosphate calibration remains held. App Formulation explanation is integrated. Pipeline PR140 is integrated on main (a0d65ac06) after exact-source green four-shard CI, local checks and raw canaries. Sean owns the subsequent full Clean→Enrich→Score run; no phase or catalog-release completion is implied. Evidence is in the existing pending-items LEDGER, October13 magnesium entry.

The [master completion plan](PHARMAGUIDE_MASTER_COMPLETION_PLAN.md), Phases 1–7, owned by the
integrator. No export-schema change mixes into it. Work that can run beside it because it touches
no shared pipeline owner: items 1.1, 1.2 and authoring the benchmark scenarios for 1.10.

Current checkpoint (October 3): D26/D24/omega source implementation, bounded
calibration, alternate-serving reconciliation and the clinical-reachability order
correction are integrated on `main` through `5246ad20` (historical source audit; subsequent accepted corrections are contained through `4f2a6509`). Exact-source four-shard CI
and the local corpus gate are green. The accepted 344-label calibration replay and
the later 137-affected-plus-35-control reachability replay have zero typed-safety,
scoring-status or route regressions. The accepted fresh full Clean/Enrich/Score
run completed 37 brand directories plus Product Submissions with38 complete
stage chains and114 current manifests. Phase0 still waits on release gates,
rebuilt app rendering verification and exact candidate approval; no runtime
publication is complete.

### Phase 1 — truth reconciliation

- [ ] **1.1 Website claims match the engine.** Verified over-claims at `web:` commit `8bfb775` [V]:
  "FDA · NIH · PubMed verified" (`src/components/sections/Hero.tsx`); a 4-pillar score and "purity"
  (`src/lib/features.ts`, `src/components/sections/YourFit.tsx`); proprietary blends "decomposed"
  into estimated per-ingredient ranges (`src/lib/features.ts`, `src/lib/methodology.ts`); FAERS
  signals "surfaced in-app" (`src/lib/features.ts`, `src/lib/methodology.ts`), while the pipeline
  deliberately does not export adverse-event signals (`scripts/build_final_db.py`, the "B8 CAERS is
  intentionally NOT surfaced" note) [V]; "Health data never leaves your device"
  (`src/components/sections/InfrastructureStrip.tsx`); CoQ10 "discussed in cardiology guidelines";
  and a "180,000+" catalog (`src/lib/site.ts`) against the 15,310 products of the live catalog
  (ledger D19). Rule: every clinical example on the site is backed by a production record or
  removed. Later slice: the site renders examples from fixtures generated by the export contract,
  so copy cannot drift again (nothing generates them today [A]).
  **First pass integrated and source pushed 2026-10-01** on website main through `02f259c`
  (includes `ba8da3c`, `0ab8541`, `2a12a2d`, `282dfa8`): pillars, blends, FAERS, lot matching, hero wording, privacy strip and the
  depletion examples (only records the app publishes as verified). Still open:
  - Privacy first pass now distinguishes local health data, RxNorm search and signed-in supplement-stack sync; any further legal policy changes remain Sean-owned.
  - The catalog-count claim was corrected in website `282dfa8`; future coverage claims still need current source/artifact evidence.
  - Homepage ladder copy was reconciled in website `0ab8541`/`282dfa8`; pipeline D27/Q50 source repairs are now on the combined integration candidate. Interaction-artifact publication still needs the release chain.
- [ ] **1.2 App safety and accuracy fixes.**
  - [x] Lookup and safety-critical admission precede the guest quota in both barcode flows (app main `b64211cd`); live recalls are rendered on the product page. The newly audited verified-feed cache repair is on the combined app candidate.
  - [x] App privacy copy reconciled on main `06a8b0eb`: core health processing is local, RxNorm search is disclosed, and signed-in supplement-stack sync remains explicit.
  - [x] Missing catalog compatibility keys/old schemas are refused; missing safety status cannot inherit legacy SAFE/POOR reassurance (app main `b64211cd`). Warning fallbacks remain conservative.
  - [x] Severity banners announce their tone (app main `b64211cd`).
  - [ ] Verify remaining verdict-badge semantics and lift the 1.4× text cap only after screen-by-screen layout checks.
  - Show an explicit "Amount not disclosed" on blend rows; today the row just shows no amount [A].
- [ ] **1.3 Analysis Coverage as one exported value.** The inputs exist: `mapped_coverage`
  (matrix concept `mapping_coverage_contract`), `scripts/scoring_v4/scored_artifact.py::_quality_assessment_status`,
  `scripts/scoring_v4/confidence.py::evaluate_confidence`, blob `v4_confidence_detail`. Compose
  them; do not build a second calculator. Coverage also leaks into the verdict in two places:
  `scripts/scoring_v4/scored_artifact.py::_public_verdict` turns SAFE into CAUTION below
  `LOW_COVERAGE_TRUST_FLOOR` [V], and `app:lib/core/components/pg_hero_section.dart::heroScoreDisplayFor`
  hides a pipeline score when coverage is low [V]. Separating them moves verdicts, so it goes
  through `/pg-scoring-change`. New export field: Sean + ADR.
  - October 25 detail repair removes proprietary-blend disclosure from the app's global coverage card: undisclosed component amounts remain a local ingredient/score limitation, while global partial coverage now requires an actual mapping or ledger gap. This reuses the existing coverage contract and adds no field or calculator. Exact-head CI and rebuilt-catalog/device acceptance remain before closing 1.3.
- [ ] **1.4 Three-part result header and page order.** Identity → critical status → personal card →
  PG Score → coverage → ingredients → interactions → evidence → verification and label history.
  The app already has the compact six-bar card (`app:lib/core/components/pg_score_breakdown_card.dart`)
  and a built-but-unmounted label-confidence section (`buildLabelConfidenceSection`, defined and
  never called) [V].
  `not_scored` products remain excluded from the shipped catalog, so no new
  public explanation contract is required for them.
- [ ] **1.5 Personal card.** Today `app:lib/features/product_detail/v2/sections/review_before_use_section.dart::buildProfileRelevanceSummary`
  already leads with safety and caps goal tiers under a caution [V]. Add: a separate goal line shown
  only on a match; the trigger trail ("your medication + this ingredient + this dose") by wiring the
  existing unused `buildInteractionContextLine` [V]; the current stack in the verdict (today stack
  interactions appear only in the pre-add sheet [A]); an all-clear bounded by coverage ("no conflicts
  found within reviewed coverage"). Remove the unused /20 arithmetic (`scoreFit20`, `e2cPenalty`,
  `maxPossible` in `app:lib/services/fit_score/`), which no screen reads [V], after the dead-code
  proof AGENTS.md requires. "Works against your goal" needs pipeline-authored data first.
  - October 25 detail repair makes clean `No known concerns` a compact expandable row and keeps warning/danger rows expanded. Good-to-Know and prominent score layouts are compacted through their shared components; exact-head CI and connected-device acceptance remain before closing 1.5.

October15 receipt checkpoint: pipeline PR145 merged c72607e09 with the verified PR142/144 source and receipt work; app PR122 is integrated57ab077b. Six pillar receipts reconcile and render, including real-product narrow-width/text-scale checks. This implements the receipt portion of1.6; remaining provenance/presentation requirements and final rebuilt-catalog acceptance keep the full box open. Step4 scoring consolidation remains partial; next are production missing-data/completion and bound-aware consumers, then the remaining approved ownership/config and probiotic copy changes. Sean authorized source integration/branch cleanup, while rebuild and release remain held.

- [ ] **1.6 Why this score.** One ledger per pillar in public pillar points (rule id, delta, reason,
  ingredient, source). Implemented receipts extend `quality_pillars_v4` with reconciled public
  pillar points; legacy tradeoffs remain a separate raw-module projection. Complete remaining
  ingredient/source attribution and final catalog acceptance. Pillar wording is pipeline-authored; the app's
  universal scale (`app:lib/core/scoring/v4_pillars.dart::statusForPillar`: Strong, Mixed, Limited
  by percentage) [A] is retired.
- [ ] **1.7 Interaction and depletion rule typing.** Ledger Q26 (`dose_evidence`: studied dose kept
  apart from activation threshold) and D8 (floors resting on a studied dose); a version per rule;
  reviewer and review date on every sub-rule so the app can show "Reviewed <date>" (most sub-rules
  lack one [A]). Depletion records keep "association" apart from "supplementation evidence" as
  structured fields (today both are narrative [A]; ledger Q7, Q12). Per-claim citations come after
  Q26, as their own decision.
- [ ] **1.8 Citation governance.** The strict gates already block a release
  (`scripts/api_audit/verify_interaction_rules_citations.py`, `scripts/api_audit/verify_backed_studies_citations.py`; ledger D6).
  Burn down the Q22 backlog, then make `scripts/api_audit/verify_all_citations_content.py` a full
  gate. Every published clinical record names a human reviewer; an AI audit is recorded as reviewer
  on some depletion records today [A].
- [ ] **1.9 Export versioning.** Add interaction and ruleset versions to the catalog manifest and
  set `min_app_version` from real compatibility (it is a constant in `scripts/build_final_db.py`) [V].
  This is item B3 of the July signal roadmap.
- [ ] **1.10 Gold benchmark.** 300–500 adversarial scenarios (anticoagulants, thyroid, SSRIs,
  statins, diabetes drugs, antibiotics, pregnancy, kidney disease, surgery, iron, calcium,
  magnesium, potassium, vitamins A/D/K, zinc, selenium, St John's wort, ginkgo, green tea, omega-3,
  probiotics, proprietary blends, branded aliases, missing amounts, panel zeros, reformulations).
  Extend the existing fixtures instead of starting a new suite: `scripts/data/profile_gate_test_cases.json`
  (already hash-pinned in both repos), `scripts/data/canary_products.json`, the reviewer benchmark
  (ledger D15). Runs in the release rung and in the app. Metrics: severe-interaction recall,
  false-severe rate, identity/form/dose resolution accuracy, citation validity, unknown-to-zero
  errors, cross-platform parity, score reproducibility.

### Phase 2 — Stack Impact, then the external beta

- [ ] **2.1 Stack Impact.** Before "Add to stack", show what changes: nutrient totals (zinc 24 →
  44 mg/day), UL headroom, new or resolved interactions, timing conflicts, depletion context, and
  what could not be checked. Build it as a before/after diff of the typed signal set for
  `stack` versus `stack + candidate`, reusing what exists: `app:lib/services/signals/stack_signal_aggregator.dart`,
  stable signal IDs, the lifecycle diff in `app:lib/features/history/providers/clinical_signal_lifecycle_provider.dart`,
  `app:lib/features/stack/providers/stack_safety_providers.dart::safetyCheckForAddProvider`,
  `app:lib/services/stack/stack_nutrient_aggregator.dart`, `app:lib/services/stack/stack_ul_checker.dart`.
  One diff engine serves Stack Impact now and Change Watch later.
- [ ] **2.2 Stack status without a score.** `app:lib/services/stack/stack_safety_scorer.dart`
  (100 − penalties + bonuses) is still computed by `stack_intelligence_engine.dart` [V]; replace it with disposition counts
  per the July decision.
- [ ] **2.3 Pipeline support.** UL form scope beyond the few nutrients that carry it in
  `scripts/data/rda_optimal_uls.json` [A]; timing rollup (ledger Q9).
- [ ] **2.4 Clinician brief.** A one-screen summary and a plain-text version on top of
  `app:lib/services/sharing/clinician_pdf_builder.dart`, with coverage-bounded wording.
- [ ] **2.5 External beta.** Collect false positives and negatives, scan misses, no-result searches
  and wording problems. Gate: 1.10 passes and the Phase 0 catalog is released. Since 2026-10-10 a
  small invited TestFlight beta (Launch track L7) comes first; this gate now applies to opening the
  beta beyond invited testers.

### Phase 3 — product and version intelligence

- [ ] **3.1 Formula history.** `scripts/label_record_contract.py::formula_fingerprint` and
  `_history_entries` read `label_record_snapshots`, which nothing writes [V]. Write snapshots (the
  sync already classifies label changes: `scripts/dsld_api_sync.py::classify_label_change`), keep
  history instead of overwriting, and show "Formula changed" in the app.
- [ ] **3.2 Market status.** `product_status` and `discontinued_date` come from DSLD's off-market
  flag [A]; add a last-verified date. KPI: scan match rate on currently sold products, not catalog
  rows. Needs privacy-preserving not-found counts; replay priority = risk × frequency × ambiguity.
- [ ] **3.3 Submission flywheel.** The flow exists (`scripts/submission_review/`, app submission
  sheet, human review). Add a confidence-aware confirm step in the app and finish ledger Q10, Q16.
  Submission import/mapping corrections are integrated (2026-10-22, PR242; four CI shards green,
  70-label replay and local checks passed). The existing pending-items LEDGER retains the evidence;
  catalog regeneration and the remaining flywheel work are still open.

### Phase 4 — Change Watch

After beta data, per the July guardrail. Recall alerts, safety push and the on-device lifecycle log
exist [A]. Add: Home "What changed", notices for rule and evidence changes, formula changes (needs
3.1) and certification changes.

### Phase 5 — Ask PharmaGuide

After 1.6. The assistant reads structured engine results (score ledger, Stack Impact, rules,
sources, coverage, limits) and explains them; it never decides. Decide the privacy model first:
Settings currently promises answers on this device [A].

### Phase 6 — professional and API layer

Only after the consumer engine is proven in beta. Structured identity, score, interaction results,
evidence, coverage, stack deltas and versions.

## Not building

Food or beauty scanning; a social feed; a supplement marketplace; a protocol library; an open-ended
AI health coach; AI-generated interaction rules; a home-grown drug–drug database beyond the curated
pairs; proprietary-blend dose estimation; individual outcome prediction; a complete biochemical
ontology. Examine's API is never ingested (its terms forbid it, see below).

## Decisions taken (business team, 2026-10-01, forwarded by Sean)

| Topic | Decision | Applies to |
|---|---|---|
| Score arithmetic | Keep category rescaling and the Verification 6/15 neutral baseline during Phase 0. In master-plan Phase 5, replay three Verification options (A current 6/15, B zero baseline, C reduced baseline) and the rescaling, measuring mean/median change, tier crossings, category effects, controls, products entering Poor/Excellent, claim-only versus registry-certified products. Public wording until then: "a 100-point score of six weighted dimensions, each with a defined maximum", never "raw additive points". Keep showing the numbers (84.5/100, 18/20 ...). | 1.6, master plan Phase 5 |
| Pillar wording | Pipeline exports dimension-specific labels (Evidence: Strong/Moderate/Limited; Verification: Strong/Partial/Limited; Transparency: High/Moderate/Low; Dose: Well aligned/Mixed/Poorly aligned). | 1.6 |
| Analysis Coverage | Build one pipeline-owned value (High/Moderate/Limited, percentage in details). Remove coverage from the safety verdict: CAUTION means a reason for caution was found, never "we don't know enough". Remove the app's own low-coverage score hiding; the pipeline owns scorability ("Not scored"). | 1.3 |
| Personal Fit | On the phone; delete the unused /20 math; never show a personal number. | 1.5 |
| Stack score | Retire the composite stack score; show disposition counts plus highest severity. | 2.2 |
| Drug–drug | Keep the curated pairs; never market comprehensive DDI checking; all-clear copy is coverage-aware ("No additional reviewed interactions identified within PharmaGuide's current coverage"); license a mature source later if needed. | 1.2, copy |
| Catalog number | See "Decisions already made" (NIH source wording, no product count). Long-term metric: share of scanned products resolved instantly. | 1.1, 3.2 |
| Adverse events | Not in the consumer app yet. Keep internal ingestion for research and review priority. Consumer copy: "FDA recalls and safety monitoring". | 1.1 |
| CoQ10 + statins | Resolved first-hand: the 2026 ACC/AHA dyslipidemia guideline rates routine CoQ10 for statin-attributed muscle symptoms Class 3: No Benefit. Keep the depletion record (biology); never imply supplementation. | 1.1, ledger Q52 |
| Examine | Outside the canonical pipeline under current terms; only under a negotiated agreement. | — |
| Privacy | Local by default (Personal Fit, condition gating, core stack rules, health profile); explicit network services (RxNorm lookup, optional account sync, catalog/recall updates, future AI). Ask PharmaGuide is hybrid: answer from structured engine output where possible; cloud only when invoked, minimum context, disclosed, no training. Claim: "Core Personal Fit and stack safety logic runs on your device." | 1.2, Phase 5 |
| Pricing | Never paywall a critical safety finding (recall, contraindication, avoid, unsafe accumulation). Premium monetizes history, Change Watch, advanced Stack Impact, profiles, AI, comparisons, reports, sync. Exact price after beta. | — |
| Fail-open and guest recall | Absolute P0, beside each other: lookup and critical safety before any quota; safety uncertainty fails closed with "Current safety status unavailable", never positive reassurance. | 1.2 |
| Human reviewer | Required on every published clinical record (reviewed_by human + reviewed_at); AI provenance kept as audited_by, never as the accountable reviewer. Before external beta. **Updated 2026-10-10:** Laurie has reviewed the content; new work is verified by the agents (Launch track L4). | 1.8 |
| Gold benchmark | Start authoring now: about 100 interaction/safety, 80 identity/form/strain, 60 dose/UL, 40 condition/profile, 40 proprietary/missing data, 30 recall/regulatory, 30 scoring controls, 20 formula/version cases, each with expected verdict, score presence, critical flags, severity, evidence tier, coverage, identity, dose resolution and citation requirements. | 1.10 |
| Rule schema | Target fields: rule_id, rule_version, entities, severity, evidence_level, presence/dose based, studied_dose, activation_threshold, threshold_basis, form/population/route scope, mechanism, clinical_effect, action, sources, reviewed_by, reviewed_at. | 1.7 |
| Formula history | Activate the existing snapshot writer; never overwrite history. | 3.1 |
| Stack Impact diff contract | Explicit now and reused by Change Watch: added_signals, removed_signals, changed_signals (before/after severity, before/after evidence, reason), nutrient_deltas, timing_deltas, coverage_deltas. | 2.1, Phase 4 |
| Phase order | Unchanged: 0 → 1 → 2 → external beta → 3 → 4 → 5 → 6. Friends-and-family usability tests may run before beta. | all |

Still open: **goal conflict data** ("works against your goal") as a pipeline-authored field (1.5).

## Status of each recommendation

Pipeline (numbering follows the strategists' Part III):

| # | Recommendation | Status | Where it goes |
|---|---|---|---|
| 1, 4, 5 | One authority; safety gate before score; personal context outside the score | Have | — |
| 2 | Literal six-pillar points | Differs by design | Decision 1 |
| 3, 31 | Every point attributable; explanation payloads | Partial | 1.6 |
| 6 | Analysis Coverage | Partial | 1.3 |
| 7 | Unknown stays unknown | Partial: `scripts/identity/interaction.py::label_row_establishes_presence`; ledger Q23 needs the re-clean, D24 open | Phase 0, 1.2 |
| 8 | Proprietary blends: no dose guessing | Have in pipeline [A]; website claims otherwise | 1.1 |
| 9, 20, 21 | Typed interaction rules; atomic claims; depletion split | Partial | 1.7 |
| 10, 11, 12 | Evidence transfer boundaries; Evidence vs Dose; role and prominence | In progress | Phase 0 |
| 13, 14 | Verification hierarchy; label analysis is not lab testing | Have (`scripts/scoring_v4/cert_evidence.py`); website wording | 1.1, Decision 1 |
| 15, 16 | Product fingerprint; market status | Partial | 3.1, 3.2 |
| 17 | Label truth beside normalized identity | Have [A] | — |
| 18, 19, 25 | Discovery vs publication; strict citation gate; LLM outside clinical authority | Mostly have | 1.8 |
| 22 | Nutrient-specific UL scope | Partial | 2.3 |
| 23 | Recalls separate from adverse-event signals | Have; signals stay internal (`scripts/api_audit/ingest_caers.py`) | Decision 5 |
| 24 | No Examine ingestion | Have | — |
| 26, 27 | Gold benchmark; weighted replay | Partial | 1.10, 3.2 |
| 28 | Score-change audit | Have (`scripts/audits/quality_redesign/replay.py`, `scripts/release_safety/catalog_diff.py`) | — |
| 29, 30 | Versioned contract; website fixtures from the export | Partial; missing | 1.9, 1.1 |
| 32 | Change Watch | Partial (app lifecycle log) | Phase 4 |
| 33 | Do not expand drug–drug | Small curated set exists | Decision 3 |

App (numbering follows Part II):

| # | Recommendation | Status | Where it goes |
|---|---|---|---|
| 1, 4 | Three states at the top; page order | Partial | 1.4 |
| 2, 3 | Gate presentation; never change the score per user | Have; NOT_SCORED copy thin | 1.4 |
| 5, 6 | Compact six bars; pillar-specific wording | Have; missing | 1.6 |
| 7, 8 | Stack Impact with deltas | Partial (pre-add interaction sheet) | 2.1 |
| 9 | Why this applies to me | Partial (helper unused) | 1.5 |
| 10 | Analysis Coverage in the UI | Partial (section built, unmounted) | 1.3, 1.4 |
| 11 | Unknown-product capture | Have; no confirm step | 3.3 |
| 12 | Formula version awareness | Partial | 3.1 |
| 13, 14 | Change Watch; Home answers "what needs attention" | Partial | Phase 4 |
| 15, 16 | Interaction detail; severity and evidence kept apart | Have the split; no reviewer or date | 1.7 |
| 17 | Depletion wording | Have | — |
| 18 | Timing layer | Partial (card, no schedule view) | 2.3, later |
| 19 | Ask PharmaGuide | Missing | Phase 5 |
| 20 | Clinician brief | Partial (PDF) | 2.4 |
| 21, 22 | Guest mode; progressive personalization | Have; critical scan admission corrected on app main | 1.2 |
| 23 | Glass only on chrome | Have [A] | — |
| 24 | Accessibility | Partial | 1.2 |
| — | Family profiles, labs, HealthKit / Health Connect | Missing | After Phase 6; not scheduled |

## Corrections to the strategists' memo

Checked on October 1, 2026.

- **Adverse events.** FDA launched a unified system (AEMS) in March 2026 that replaces FAERS and
  other legacy systems, so "move to CAERS" is itself dated; CAERS's own status was not confirmed.
  <https://www.raps.org/news-and-articles/news-articles/2026/3/fda-consolidates-adverse-events-reporting-systems> ·
  <https://open.fda.gov/apis/food/event/>
- **Examine Connect** terms (updated July 30, 2026) forbid a competing product, caching beyond
  24 hours, a reference database, and RAG or training use. <https://connect.examine.com/terms>
- **SuppCo** was acquired by Function Health (announced May 12, 2026) and now runs laboratory
  testing as a brand certification programme. <https://www.prnewswire.com/news-releases/function-acquires-suppco-to-bring-trust-and-clarity-to-supplements-302769718.html> ·
  <https://supp.co/about/tested>
- **Supplement use.** 60.2% (38.7% two or more) is adults aged 20 and over, past 30 days.
  <https://www.cdc.gov/nchs/products/databriefs/db561.htm>
- **CoQ10 and statins.** The 2026 ACC/AHA dyslipidemia guideline is reported to recommend against
  routine CoQ10 for statin muscle symptoms, confirmed only through a secondary summary. Read the
  guideline before quoting it. <https://www.jacc.org/doi/10.1016/j.jacc.2025.11.016>
- **DSLD** is run by NIH ODS, not FDA, and its API exposes `offMarket` and `entryDate`.
  <https://api.ods.od.nih.gov/dsld/v9/label/1000>
- **Fullscript Assist** is a practitioner tool. **Prove It**'s $69.99 annual price was not confirmed.
- **Also relevant:** FDA's January 2026 Clinical Decision Support and General Wellness guidances
  (reference for claims wording) <https://www.ropesgray.com/en/insights/alerts/2026/01/fda-adapts-with-the-times-on-digital-health-updated-guidances-on-general-wellness-products>;
  the Dietary Supplement Listing Act of 2026 is pending, not law
  <https://www.nutraingredients.com/Article/2026/04/21/dietary-supplement-listing-bill-introduced-in-the-house/>;
  NIH ODS "Supplements, Facts First" challenge <https://www.herox.com/SupplementsFactsFirst>.

## Owner Check

- Owner: `scripts/audits/pending_items_20260926/LEDGER.md` — evidence: read October 1; rows S1.1–S6.
- Owner of coverage inputs: `scripts/scoring_v4/confidence.py::evaluate_confidence`,
  `scripts/scoring_v4/scored_artifact.py::_quality_assessment_status` — evidence: `rg` October 1.
- Owner of formula identity: `scripts/label_record_contract.py::formula_fingerprint` — evidence: `rg` October 1.
- Owner of change tracking: `app:lib/features/history/providers/clinical_signal_lifecycle_provider.dart` — evidence: `rg` October 1.
- Will NOT create: a second register, scorer, coverage calculator, diff engine or fingerprint; an
  app-side verdict; any export field without Sean and an ADR.

### October 4 exact-candidate checkpoint

Reviewed preparation/source remediation and structural-total Formulation eligibility are integrated and green on exact CI/local checks. The4f2a6509 fullcorpus/114manifest and15,421-product strictreachability receipts passed. Latermain dd2769ad adds nutrient-conversion and safety-reason fixes plus Dose/UL and regulatory benchmark coverage; its CI passed. Fresh final artifacts, snapshot movement review, local release/full gates and real Flutter rendering remain open. These focused gold sets do not establish the entire300–500scenario beta benchmark or beta readiness. Phase0 source implementation/calibration and final release validation remain distinct. See the master plan and existing LEDGER for exact receipts. No external catalog publication.


October 4 handoff: current runtime6ea851dc corpus and strict reachability are verified; local candidate2026.10.04.133540 is imported for development. Release backstop124 passed. Full backstop found38 failures; all classes now have focused test-only remediation receipts in the LEDGER. Sean stopped broad validation; automation is paused. Replacement full validation, completed Flutter checks, actual-device rendering and human movement/publication approval remain open. No new corpus run is needed for the test/docs batch.

October12 next-release mapping follow-up:14held product identities, including all four Nature's Way hemp labels, resolve in bounded native checks. No full catalog rebuild/publication. All1474numeric form ratings unchanged; cannabinoid composition and existing clinical holds remain explicit.16frozen raw products plus three controls checked;86exact-name affected labels require next-release movement review. Source-only batch is implemented, measured, independently reviewed and validation-complete and integrated in PR119 at586d02f6: finalrolelocal546passed/24declaredskips, exact combined12556362 CI38290828456 all four groups green;94current-main/canary/source checks pass. No numeric ratings or clinical policy change. Required future Clean/catalog/app/release acceptance is recorded in the existing LEDGER and private audit REPORT; this mapping batch does not rebuild or publish delivery artifacts.

October 12 form/unit follow-up: PR120 merged 5a58f3fd2. Sean approved three provisional form ceilings of 11 and exact four-label unresolved-dose handling (including two D3 rows). The supported pipeline/app corrections and uncertainty propagation are implemented and bounded native measurements are recorded in the existing LEDGER/private REPORT. Seven exact clinical calibrations and manufacturer-unit confirmation remain unresolved; no full catalog rebuild or publication. Independent review closed; named pipeline373+908/app82+52 pass, local546 pass/24 declared skips, analyzer clean. App PR109 exact CI passed (3748 Linux tests); pipeline PR123 replacement exact CI38300540250 passed after17 old assertions were reconciled. Five additional parent controls record HMB unknown-floor and HMB/taurine denominator effects. App source integrated in PR109 atdf032916; Pipeline PR123 merged at8dac43dd; source integrated, delivery acceptance pending.

October 14 post-run checkpoint: Sean completed the corpus, but the final export rejected legitimate limited evidence. Export-contract repair PR141 is merged18ef2564c after exact-source CI; source evidence and Excellent eligibility stay unchanged. All22 glycinate capsule producer records match validated expectations. App PR119 preserves evidence grades and approved manual IDs, merged13f314a0 after green exact-source CI38517203803. Shared-module fingerprints require fresh regeneration; rerun ownership is awaiting Sean’s answer. Catalog release, app bundle parity and live Codex comparison remain unchecked; no deployment is claimed.



October 14 bounded shilajit label qualification: PR142 source da1bc55f preserves recognized aliases and accepted sugar/count corrections, and closes preparation-specific shilajit/peppermint Evidence transfer. Native Meru55.7/100 (13.3/11.4/0/15/6/10); research remains reference context where label applicability is unestablished.6,585 frozen labels reviewed,375 explained score changes; identities/amounts/safety/status unchanged. Final named1,458 tests, CI20,749/192declaredskips and local546/24declaredoptinskips pass; independent review closed. Source/measurement complete; draft PR not integrated, corpus not rebuilt or released. Concurrent main policy reconciliation and final delivery validation remain; no launch-track box is closed. Details: existing LEDGER/research and private clinical RESULT.


October22 catalog-assessment checkpoint: shared optional-use Dose policy is integrated(PR240),
not product-specific. Evidence/explanation batch PR241 and paired Flutter PR133 preserve research
context, honest unknowns, source-qualified daily-use warnings and comparison qualifications.
8283stored products and1332distinct raw labels measured; no additional numeric score or safety
changes. Source integrated: pipeline PR241 at14215663e, app PR133 at657c7c0e; exact
candidate CI/local/review passed, recorded in the existing pending-items LEDGER. Combination clinical attribution remains an explicit hold.
Sean runs the necessary Clean-first pipeline-only regeneration after integration; catalog parity,
canary refresh and real-device Flutter acceptance remain release gates. No pipeline/release run
by this lane, and no launch phase is marked complete from these checks.

October23 follow-up: all ten quality holds audited; twelve actual export blobs succeed with honest withheld scores preserved. Verified correction provenance resolves213846; TiO2 color-purpose assessment restored at existing owner. New submission photo audit found reviewer-owned corrections and S12 unreadable text; those remain open before approval. [Audit](../../scripts/audits/holds_submissions_20261023/README.md). No pipeline or release ran.

October 27 returned-review follow-up: 49 backed records reconciled; 343 valid Dose-only proofs. Signed lutein rejection and migraine-scoped B2 use close two source holds. Required subjects: 28/146 complete, 118 held. All 252 frozen dependencies checked: 25/46 preparation groups complete or outside botanical Dose, 21 held. Real-label baseline/candidate measurements and source/access exceptions are in the existing pending-items LEDGER. No new authority, weights, whole pipeline or publication; no launch box closed. Final CI 40623051441 passed on 269e45868 (25,079 tests and declared-skip checks); PR 269 integrated at f6439191b. Clean-first compute-only regeneration, rebuilt-corpus/app acceptance and remaining scientific holds are separate.
