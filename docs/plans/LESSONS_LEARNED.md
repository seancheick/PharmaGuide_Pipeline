---
title: Pipeline Dashboard — Lessons Learned
tags:
  - retrospective
  - pipeline-dashboard
  - learning
related:
  - "[[pipeline-dashboard-sprint-tracker]]"
---

# Pipeline Dashboard — Lessons Learned

This document is updated after each sprint. It captures what went well, what went wrong, and what to change next time.

> [!info] Linked from
> - [[pipeline-dashboard-sprint-tracker]] — Sprint execution tracker (source of truth for tasks)

## Reconciliation Note (2026-04-09)

- This file was backfilled during Sprint 15 from the tracker, code audit, tests, and correction-sprint verification evidence.
- Dates before Sprint 15 are retrospective, not contemporaneous sprint notes.
- Where the first implementation overclaimed completion, the notes below call that out explicitly and point to what changed in the correction sprint.

---

## Sprint 0

**Dates:** 2026-04-08 (retrospective backfill on 2026-04-09)
**What went well:**
- The dashboard scaffold matched the planned directory layout and gave later sprints a stable place to land.
- Keeping the app read-only from day one kept the architecture simple.

**What went wrong:**
- Verification evidence was not preserved well enough at sprint time, which later forced a reconciliation pass.

**What we'd change:**
- Save a screenshot or terminal proof as soon as the first app launch works.

---

## Sprint 1

**Dates:** 2026-04-08 to 2026-04-09 (retrospective backfill)
**What went well:**
- The loader started from real workspace artifacts instead of assuming an idealized report layout.
- Read-only SQLite access and missing-file tolerance were the right defaults.

**What went wrong:**
- The artifact layout in the workspace was less uniform than the original plan assumed.

**What we'd change:**
- Normalize discovery rules and shared metrics earlier so later views do not reinvent them.

---

## Sprint 2

**Dates:** 2026-04-08 to 2026-04-09 (retrospective backfill)
**What went well:**
- The sidebar shell gave the dashboard a clear operator-oriented structure.
- Query-param support made deep-linking possible for the inspector.

**What went wrong:**
- Refresh behavior was initially incomplete and later required a cache-resource fix in the correction sprint.

**What we'd change:**
- Add an app-shell smoke test as soon as navigation and refresh are introduced.

---

## Sprint 3

**Dates:** 2026-04-08 to 2026-04-09 (retrospective backfill)
**What went well:**
- Reusable components reduced repetition across the early views.
- Small UI primitives made later corrections cheaper than a large monolithic view layer.

**What went wrong:**
- Component completion was inferred from file presence more than explicit view-level verification.

**What we'd change:**
- Pair every new reusable component with one direct render smoke test.

---

## Sprint 4

**Dates:** 2026-04-09 (retrospective backfill)
**What went well:**
- SQL-backed search and deep linking gave the inspector immediate practical value.
- Limiting queries kept the view fast enough for local use.

**What went wrong:**
- Search verification was recorded broadly, but not with enough persistent evidence.

**What we'd change:**
- Keep one saved deep-link example in the tracker or docs.

---

## Sprint 5

**Dates:** 2026-04-09 (retrospective backfill)
**What went well:**
- The drill-down view successfully connected DB rows, detail blobs, and score trace context.

**What went wrong:**
- A real bug remained in the inspector because `sqlite3.Row` was treated like a dict with `.get()`. That was fixed in the Sprint 15 correction sprint.

**What we'd change:**
- Add one real-product drill-down test the same sprint the panel ships.

---

## Sprint 6

**Dates:** 2026-04-09 (retrospective backfill)
**What went well:**
- The health view established the core release-gate and artifact-health workflow operators needed.

**What went wrong:**
- Several health metrics were still view-local and later had to be normalized in the loader.

**What we'd change:**
- Put release-gate inputs in the loader before rendering Health, Quality, and Observability.

---

## Sprint 7

**Dates:** 2026-04-09 (retrospective backfill)
**What went well:**
- The quality queue, unmapped hotspots, and fallback visibility aligned well with the original operator use case.

**What went wrong:**
- The real dataset output layout forced more fallback discovery logic than the sprint plan assumed.

**What we'd change:**
- Test against multiple real dataset output shapes during the same sprint.

---

## Sprint 8

**Dates:** 2026-04-09 (retrospective backfill)
**What went well:**
- Distribution charts and safety summaries made the quality view substantially more usable.

**What went wrong:**
- Coverage semantics and shared metric sourcing were still fragmented before the correction sprint normalized them.

**What we'd change:**
- Do not let charts compute their own versions of core release metrics.

---

## Sprint 9 (Phase 1-2 Gate)

**Dates:** 2026-04-09 (retrospective backfill)
**What went well:**
- The project did stop to do an integration pass before pushing further into late-stage views.

**What went wrong:**
- The tracker overstated the strength of that gate. Screenshots were not actually preserved, and some bugs survived the sprint.

**What we'd change:**
- Treat phase gates as evidence checkpoints, not just a narrative milestone.

**Gate Review Notes:**
- The original phase-gate claim was corrected during Sprint 15 after the refresh bug, missing screenshots, and evidence gaps were re-audited.

---

## Sprint 10

**Dates:** 2026-04-09 (retrospective backfill, corrected in Sprint 15)
**What went well:**
- The observability tab structure was a useful foundation and kept later additions contained.

**What went wrong:**
- The first implementation under-delivered versus the spec. Sankey labeling, classified error drill-down, and richer mismatch evidence were added later in the correction sprint.

**What we'd change:**
- Do not mark an observability sprint complete until the operator can diagnose a failure from the UI alone.

---

## Sprint 11

**Dates:** 2026-04-09 (retrospective backfill, corrected in Sprint 15)
**What went well:**
- Safety and storage concerns were put into the right operational home inside Observability.

**What went wrong:**
- Sync and cleanup behavior needed clearer graceful-degradation and preview semantics than the first pass provided.

**What we'd change:**
- Make the "preview-only, never delete" rule explicit in both code and docs from the first implementation.

---

## Sprint 12

**Dates:** 2026-04-09 (retrospective backfill, corrected in Sprint 15)
**What went well:**
- The analytics scope was directionally right: drift, alerts, trends, completeness, and bottlenecks all belonged together.

**What went wrong:**
- The workspace only had a single build, so multi-build verification was weaker than the tracker implied.
- A loader-level build history abstraction was missing until the correction sprint.

**What we'd change:**
- Build history and threshold loading should be platform primitives, not late view logic.

---

## Sprint 13

**Dates:** 2026-04-09 (retrospective backfill)
**What went well:**
- Diff views made the dashboard materially more useful for release comparison.

**What went wrong:**
- The original plan assumed a cleaner release-selection flow than the first implementation delivered.

**What we'd change:**
- Validate diff UX with at least two real build roots before calling the sprint complete.

---

## Sprint 14

**Dates:** 2026-04-09 (retrospective backfill, corrected in Sprint 15)
**What went well:**
- The intelligence area was the right place to aggregate category, brand, and scoring insights.

**What went wrong:**
- The first pass was incomplete relative to the spec. The why-top explainer, high-risk ingredient view, and substring ingredient search were finished in the correction sprint.

**What we'd change:**
- Late-stage analytical views need explicit acceptance criteria tied to real UI behaviors, not just table presence.

---

## Sprint 15 (Final Gate)

**Dates:** 2026-04-09 (correction sprint foundation)
**What went well:**
- Added a loader-level build history abstraction so release diff, drift checks, and monitoring all read from one source of truth.
- Normalized shared release, safety, and yield metrics in the loader so Health, Quality, and Observability stopped recomputing conflicting values.
- Added a dashboard smoke suite that imports and renders all views with mocked Streamlit, reducing regression risk.
- Added empty-export verification, a live Streamlit HTTP check, and clearer operator docs so handoff is less dependent on tribal knowledge.
- The UX refresh replaced the flat Streamlit shell with a grouped executive dashboard shell, a `Command Center`, readable timestamps, and explicit data-source context across pages.

**What went wrong:**
- The sprint tracker had drifted ahead of the implementation reality, so the correction sprint had to repair both code and planning artifacts before final handoff work.
- Real workspace artifacts differ from the idealized report layout in the original plan, which forced the dashboard to support logs and output directories more flexibly.

**What we'd change:**
- Add smoke coverage and normalized loader abstractions much earlier, before building late-stage dashboard views.
- Require concrete verification evidence in the tracker at the end of each sprint so plan drift is caught before it compounds.
- Introduce shared UI shell primitives earlier so later view work does not accumulate dated UX debt.

**Final Review Notes:**
- 2026-04-09 reviewer re-check: no remaining material code or documentation blockers beyond the manual screenshot artifact and recording formal sign-off evidence.
- Manual screenshot capture is now documented in `scripts/dashboard/INSTRUCTIONS.md`, so the remaining handoff work is operational rather than implementation-related.
- 2026-04-09 UX refresh verification: navigation, page metadata, app shell, time formatting, and command-center coverage were added and verified in the expanded dashboard suite.

---

## Session: 2026-04-14 — Interaction Safety Expansion

**Scope:** Citation integrity, IQM expansion, context-aware scoring, interaction rules overhaul

### What went well

1. **Hallucinated PMID detection pattern works.** `verify_all_citations_content.py` caught 25 PMIDs that existed in PubMed but were about completely different topics. PMID existence alone proves nothing — content verification (checking the paper title actually matches the claimed topic) is essential. Always run content verification after any AI-generated citation.

2. **SUPPai CUI alias mapping at scale.** Adding 131 CUI aliases to 86 IQM entries unlocked 1,573 SUPPai research pairs. The bottleneck was string identity mismatches (e.g., SUPPai uses CUI C3540037 "Calcium Supplement" while IQM uses "calcium"). Alias expansion is high-ROI, low-risk work.

3. **Cross-DB overlap allowlist caught real issues.** When we added canola oil and MSG to IQM, the test guard instantly flagged overlaps with harmful_additives. The test-time guard pattern (fail-on-overlap, force human review) works exactly as designed.

4. **Context-aware harmful scoring was the right call.** Research confirmed no major platform dual-scores an ingredient as both quality bonus AND safety penalty. The fix was surgical: 2 files changed, 10 new tests, zero regressions. The enricher tags source_section, the scorer suppresses active-source precautionary penalties.

5. **Interaction rules gap analysis found critical safety holes.** Ginkgo was missing its #1 interaction (anticoagulants), SJW was missing SSRI serotonin syndrome, and magnesium was missing kidney_disease. These are life-safety bugs in a medical app.

### What went wrong

1. **Original interaction rules had undocumented severity values.** The taxonomy defines `monitor`, `info`, and `theoretical` as valid, but my initial validator only checked `caution/avoid/contraindicated`. Pre-existing rules using `monitor` looked like errors. Lesson: always read the full taxonomy before writing validators.

2. **SUPPai "new entries" list needed heavy manual triage.** The gap analysis flagged 300 "new" supplements, but ~50% were hormones, metabolites, lab markers, or drugs (ACTH, glucose, progesterone, procaine). Blindly adding them would have polluted the IQM. Each "new entry" candidate needs a human judgment call: is this actually a dietary supplement?

3. **Some easy-map matches were wrong.** Token-overlap matching incorrectly suggested Glycerol → monolaurin, Linolenic acid → gamma_linolenic_acid, and CLA → linoleic acid. These are chemically distinct compounds that share words. Fuzzy matching needs chemistry-aware review.

### Lessons for future sessions

1. **PMID content verification is non-negotiable.** Run `verify_all_citations_content.py` after ANY data file change that involves PMIDs. AI-generated PMIDs pass existence checks but fail content checks ~30% of the time.

2. **IQM alias additions are safe to batch (additive-only).** Adding CUI aliases to existing entries has zero risk — it only expands matching, never changes scoring. New entries need full schema validation and API verification.

3. **Harmful additive penalties should be section-aware.** If an ingredient is in Supplement Facts (active), the IQM quality score is the correct signal. Additive penalties should only fire for Other Ingredients (inactive), with high/critical severity as the exception.

4. **Drug class gaps block entire categories of interaction.** Missing the SSRI/SNRI class meant SJW serotonin syndrome — one of the most documented herb-drug interactions — was invisible. When adding new interaction rules, always check if the needed drug class exists first.

5. **The interaction rules file is the most impactful safety artifact.** It determines what warnings 5,231 products show to users with health conditions. Any gap = silent failure for real patients. Schedule quarterly audits against clinical literature updates.
