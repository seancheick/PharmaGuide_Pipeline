# Handoff — Next Session Starting Line

> **Purpose:** thin tactical doc. "Where we stand + what's the resumed trajectory."
> The authoritative plan is [`docs/AUTOMATION_ROADMAP.md`](AUTOMATION_ROADMAP.md).
> Session journals (archived, don't edit):
>
> - [HANDOFF_2026-04-18.md](HANDOFF_2026-04-18.md) — Dr Pham clinical review + roadmap authoring
> - [HANDOFF_2026-04-20_PIPELINE_REFACTOR.md](HANDOFF_2026-04-20_PIPELINE_REFACTOR.md) — Sprint D accuracy sprint (SHIPPED)

---

## What just happened

Sprint D was an **accuracy-work detour off the AUTOMATION_ROADMAP**. It was
triggered by a deep audit that found 833 silently-mapped rows + amaranth
plant/dye confusion + B7 UL teratogenicity gap. Completed in 5 days across
D1→D5.4, shipped 2026-04-21:

- Bundled catalog **v2026.04.21.164306** (schema 1.4.0, **8,288 products**) live on Supabase
- Flutter bundled at [Pharmaguide.ai `6e6a692`](https://github.com/seancheick/Pharmaguide.ai/commit/6e6a692)
- Pipeline main HEAD: `8bf65d5`
- **4,479 tests** passing, 374 net new Sprint D regression tests

**Sprint D is now CLOSED.** Next session **resumes the AUTOMATION_ROADMAP trajectory** — the roadmap explicitly says _"Phase 1 — pipeline in CI (next agent starts here)"_.

---

## Current baseline

| Layer    | State                                                                 | Evidence                |
| -------- | --------------------------------------------------------------------- | ----------------------- |
| Pipeline | 20 brands → 13,236 enriched → 13,236 scored → 8,288 unique            | Git `8bf65d5` on main   |
| Supabase | `is_current=true` on v2026.04.21.164306                               | MCP query confirmed     |
| Flutter  | `assets/db/` bundled, checksum matches manifest                       | Git `6e6a692` on main   |
| Tests    | 4,479 pipeline + 56 Flutter test files                                | `pytest scripts/tests/` |
| Disk     | `~/Documents/DataSetDsld/builds/release_output/` retained as rollback | 1 GB                    |

---

## Medical-accuracy invariants (verified live; do not regress)

| Invariant                                                | Coverage                                  |
| -------------------------------------------------------- | ----------------------------------------- |
| `rda_ul_data.collection_enabled=true`                    | 13,236 / 13,236 (100%)                    |
| B7 OVER-UL safety_flags firing                           | 1,929 products (D4.3 teratogenicity LIVE) |
| Dr Pham `safety_warning` on banned entries               | 2,413 / 2,413 (100%)                      |
| Dr Pham `ban_context` on banned entries                  | 2,413 / 2,413 (100%)                      |
| No silent mapping (`mapped=True ⇒ canonical_id != None`) | D2.1 contract enforced                    |
| No "from X" source-descriptor rows unmapped              | D2.10 routing                             |
| Proprietary-blend rows → recognized_non_scorable         | D2.7.1                                    |
| Every frozen snapshot matches scored output              | 30 / 30                                   |

---

## Canary before next sprint starts

```bash
cd "/Users/seancheick/PharmaGuide ai"
flutter test test/release_gate/bundled_catalog_test.dart
```

Then open the app and spot-check 3 products:

| Product                                              | Expected signal                                                  |
| ---------------------------------------------------- | ---------------------------------------------------------------- |
| Thorne Silybin Phytosome (dsld 16037)                | Score ~52/80, evidence card shows milk_thistle canonical         |
| Any multivitamin with 10k+ IU Vitamin A across forms | B7 banner: _"Vitamin A exceeds UL (X%) — summed across N forms"_ |
| Any product with Titanium Dioxide                    | Layperson-facing banner (not technical jargon)                   |

Roll back via `python3 scripts/sync_to_supabase.py --force <prev_version>` if any fail.

---

## Resumed trajectory — **Sprint E1 first, then AUTOMATION_ROADMAP**

**2026-04-21 update:** A dual audit (pipeline-side label-fidelity scan + Flutter device-testing handoff) surfaced 10 accuracy/safety defects affecting ~60% of the catalog. Cannot ship public beta in current state. See [`SPRINT_E1_ACCURACY_ADDENDUM.md`](SPRINT_E1_ACCURACY_ADDENDUM.md) — prerequisite addendum, not a detour.

| Checkpoint    | What                                                      | When                        | Effort     | Reference                                       |
| ------------- | --------------------------------------------------------- | --------------------------- | ---------- | ----------------------------------------------- |
| **Sprint E1** | Accuracy addendum (label-fidelity + safety-copy)          | **START HERE**              | ~14 days   | [`SPRINT_E1_ACCURACY_ADDENDUM.md`](SPRINT_E1_ACCURACY_ADDENDUM.md) |
| Phase 1       | Pipeline runs in CI (GitHub Actions + cloud storage)      | After Sprint E1 ships       | 2–3 weeks  | § "Phase 1 — Pipeline runs without your laptop" |
| Phase 1.5     | Safety Alert Short Path (FDA recall < 15 min → user push) | **Ship before public beta** | 2–3 weeks  | § "Phase 1.5 — Safety Alert Short Path"         |
| Phase 2       | Dr. Pham web editor (PR via UI)                           | Nice-to-have for beta       | 3–4 weeks  | § "Phase 2"                                     |
| Phase 3       | Scheduled monthly DSLD category delta                     | V1 phase                    | 2 months   | § "Phase 3"                                     |
| Phase 4       | Reference-data hot-refresh                                | V1 phase                    | 2–3 months | § "Phase 4"                                     |
| Phase 4.5     | Tiered offline architecture (Yuka-style)                  | Triggered at 50k products   | 4–6 weeks  | § "Phase 4.5"                                   |
| Phase 5       | Full observability / staging / audit                      | V1 onward                   | Ongoing    | § "Phase 5"                                     |

### Sprint E1 rationale (read before skipping)

The roadmap's Phase 1 (CI automation) assumes the current data content is correct. Two independent audits on 2026-04-21 proved it isn't:

- Pipeline scan: ~1,158 products with stripped proprietary-blend masses; ~460 with branded names dropped (KSM-66 class); ~4,812 with active-count drift; ~118 with silently-dropped inactive ingredients (silica class).
- Flutter device testing: danger strings landing in `decision_highlights.positive` (green thumbs-up on "Not lawful"); pregnancy warnings shown to male users; raw enum `ban_ingredient` leaking to UI; 6× duplicate warnings; no authored copy for banned-substance stack-add preflight.

If we run Phase 1 CI on top of these defects, we automate the propagation of the bugs. Sprint E1 fixes the content first.

### Phase 1 prep checklist (from roadmap) — after E1 ships

Before opening the next PR:

1. Read [`AUTOMATION_ROADMAP.md`](AUTOMATION_ROADMAP.md) § "Phase 1" top-to-bottom.
2. Read [`PIPELINE_OPERATIONS_README.md`](PIPELINE_OPERATIONS_README.md) § Playbooks (understand what must survive CI).
3. Read [`PIPELINE_MAINTENANCE_SCHEDULE.md`](PIPELINE_MAINTENANCE_SCHEDULE.md) (roles + cadence).
4. Run the full test suite (`python3 -m pytest scripts/tests/ -q`) — 4,479 is your known-green baseline.
5. Start with **one brand** (e.g., Nature_Made). Prove the CI path end-to-end before scaling.

---

## Net-new items surfaced during Sprint D (not in AUTOMATION_ROADMAP yet)

These emerged from Sprint D work and **belong in the roadmap** — add them when you next edit `AUTOMATION_ROADMAP.md`:

1. **Release-ops automation** (`make release` one-command sequence). Not explicitly in roadmap but reduces manual 10-step recipe → 1 command. Add to Phase 1 as scaffolding.
2. **Post-sync Supabase verification** (query `export_manifest` after sync, confirm `is_current=true` matches local). Belongs in Phase 1 CI workflow.
3. **Sentry integration** (pubspec.yaml staged, uncommitted). Belongs in Phase 5 observability.
4. **Release ledger** (`docs/RELEASES.md` append-only log of each shipped version). Not in roadmap. Suggest adding to Phase 1.

---

## Non-blocking cleanup (do when convenient)

1. Commit or discard Sentry pubspec.yaml + .gitignore WIP in Flutter repo (user had staged locally, uncommitted).
2. Prune `~/Documents/DataSetDsld/builds/` older than 2 weeks (keep last 2 for rollback).
3. Refresh the stale `reference_supabase_project.md` memory to note schema 1.4.0 + 8,288-product baseline.

---

## Non-negotiable protocol rules

1. Every identifier (PMID, CUI, RXCUI) must be API-verified before shipping.
2. Every new canonical or data-file entry requires human approval — **no auto-commits of safety data.**
3. `mapped=True ⇒ canonical_id != None` — enforced mechanically.
4. Coverage gate 99.5% is the medical-safety floor — never bypass.
5. Every code change ships with a regression test in `scripts/tests/`.
6. Snapshot drifts require a changelog entry in `_manifest.json` + medically-reviewed justification.

---

_Pick up [`AUTOMATION_ROADMAP.md`](AUTOMATION_ROADMAP.md) → Phase 1. The plan already exists; do not reinvent it._
