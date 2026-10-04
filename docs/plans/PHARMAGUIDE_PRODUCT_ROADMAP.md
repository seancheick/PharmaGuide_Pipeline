# PharmaGuide product roadmap

Written October 1, 2026 from the business strategists' review (pipeline, app and market
recommendations), checked against the three repositories and the live market. Sean approved the
order below on October 1.

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

## Decisions already made

| Date | Decision |
|---|---|
| 2026-10-01 | Personal Fit stays on the phone. The pipeline writes the rules; the phone applies them. The profile never leaves the device for this. |
| 2026-10-01 | One compact personal card: a safety line always; a goal line only when the product matches a goal or works against one; nothing when neutral. |
| 2026-10-01 | The first external beta comes after Stack Impact. |
| 2026-10-01 | Business team's answers to the decision queue, forwarded by Sean; see "Decisions taken" below. |
| 2026-10-01 | Public catalog wording: the catalog is "sourced from NIH's Dietary Supplement Label Database (200,000+ labels)". No product count is shown (Sean: 15k reads as weak; 180,000+ described neither our catalog nor the source). |
| 2026-07-23 | No consumer change timeline or notifications before beta data shows the changes are meaningful (signal-lifecycle guardrail). Still in force: Change Watch UI is Phase 4. |
| 2026-07-22 | No user-facing health score for the stack; use status and concern counts. |

## Phases

### Phase 0 — finish the current remediation

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
- [ ] **1.6 Why this score.** One ledger per pillar in public pillar points (rule id, delta, reason,
  ingredient, source), extending `quality_pillars_v4[].components`. Today the exported bonuses and
  penalties (`scripts/build_final_db.py::derive_v4_tradeoffs`) are in raw module points and do not
  sum to the pillar [A]. Pillar wording becomes pillar-specific and pipeline-authored; the app's
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
  and wording problems. Gate: 1.10 passes and the Phase 0 catalog is released.

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
| Human reviewer | Required on every published clinical record (reviewed_by human + reviewed_at); AI provenance kept as audited_by, never as the accountable reviewer. Before external beta. | 1.8 |
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
