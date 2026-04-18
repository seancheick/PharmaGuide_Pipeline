# PharmaGuide — Pipeline Maintenance Schedule

**Audience:** Sean + any teammates / reviewers / clinical authors.
**Purpose:** Keep the pipeline fresh, trustworthy, and running without anyone's laptop being "the server."
**Companion docs:**
- [`AUTOMATION_ROADMAP.md`](AUTOMATION_ROADMAP.md) — phased plan to get us to full automation.
- [`PIPELINE_OPERATIONS_README.md`](PIPELINE_OPERATIONS_README.md) — the "how to actually run it" playbook.
- [`scripts/PIPELINE_MAINTENANCE_SCHEDULE.md`](../scripts/PIPELINE_MAINTENANCE_SCHEDULE.md) — technical command reference (every exact shell command).

This document is **complementary** to the technical reference in `scripts/`. That file lists every command. This file answers *who runs which command, how often, and what happens if they don't*.

---

## The mental model

Think of the pipeline as a living organism with three layers, each with its own refresh cadence:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3 — Product catalog (WHAT is on the market)          │
│  Source: NIH DSLD. Refreshes: continuously at NIH.          │
│  Our cadence: monthly delta pulls (Phase 3).                │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 2 — Reference knowledge (WHAT the rules are)         │
│  Source: FDA recalls, CAERS events, PubMed, ChEMBL, etc.    │
│  Our cadence: weekly for safety data, quarterly for science.│
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — Clinical voice (HOW we tell the user)            │
│  Source: Dr. Pham + future clinical reviewers.              │
│  Our cadence: on-demand PRs + quarterly "sweep" review.     │
└─────────────────────────────────────────────────────────────┘
```

Each layer refreshes on its own timer. The pipeline's job is to integrate all three into a single user-facing answer.

If any layer goes stale, users feel it — new products don't show up, safety warnings lag reality, or the clinical voice gets dated.

---

## Roles & responsibilities

Start solo. Add roles as needed.

| Role | Current (solo) | Phase 1 (2 people) | Phase 3+ (team) |
|---|---|---|---|
| **Pipeline operator** — runs builds, approves PRs, deploys | Sean | Sean | Sean + 1 engineer |
| **Clinical author** — authors safety/bonus copy | Dr. Pham | Dr. Pham | Dr. Pham + CSO |
| **Safety reviewer** — final approve on clinical-copy PRs | Sean | Sean | CSO |
| **Data curator** — watches DSLD intake, flags bad products | Sean | Sean | Ops contractor (part-time) |
| **Science reviewer** — validates new PMIDs, evidence levels | Sean | Sean | Dr. Pham / CSO |

**Key principle:** no role should require superuser access to your laptop. Every task below should be doable by the assigned role with only a GitHub account + a web browser (once Phase 1–2 are in place).

---

## Cadence — what happens, how often, by whom

### Daily (automated)

| Task | Who | What | Tooling |
|---|---|---|---|
| CI status check | Automated | Every PR gets `validate_safety_copy.py --strict` + `pytest` run | GitHub Actions |
| Uptime monitor | Automated | Supabase + Flutter endpoints pinged every 5 min | UptimeRobot (free) |

### Weekly (partly automated, light human)

| Task | Who | Day | Time | What it does |
|---|---|---|---|---|
| FDA recall sync | **Automated** (Phase 1 unlocks this) | Monday 4am UTC | 2 min | Pulls new FDA recalls into `banned_recalled_ingredients.json` as a draft PR; human reviews copy before merge. |
| Manufacturer violations sync | **Automated** (Phase 1) | Monday 4am UTC | 1 min | Pulls new FDA enforcement actions → draft PR. |
| Dashboard check | **Pipeline operator** | Friday EOD | 5 min | Open Clinical Copy dashboard → confirm no staleness alerts, no red coverage badges, no stale Flutter asset warnings. |

**Why weekly?** FDA publishes new recalls/enforcement actions continuously. Users reasonably expect a recalled product to show up as recalled within a week, not a quarter.

### Monthly (automated intake + human review)

| Task | Who | Day | Time | What it does |
|---|---|---|---|---|
| DSLD category delta pull | **Automated** (Phase 3) | 1st of month, 00:00 UTC | 15 min | Pulls new products from NIH DSLD by category (gummies, capsules, softgels). Opens PR: *"Monthly intake YYYY-MM: +X new products"*. |
| CAERS adverse event refresh | **Automated** (Phase 3) | 5th of month | 3 min | Re-pulls FDA CAERS data → updates adverse-event signals → rescoring. |
| UNII cache refresh | **Automated** | 5th of month | 1 min | Refreshes the 172k-substance identity cache. |
| Citation content verification | **Pipeline operator** | 10th of month | 30–45 min | Spot-check 20 PMIDs for content accuracy (no hallucinated citations). Run `verify_all_citations_content.py`. |
| Clinical-copy review queue | **Clinical author (Dr. Pham)** | Any time | 2–4 hrs | Work through the dashboard's "needs review" queue — entries flagged by the validator or manually queued. |
| Intake PR review | **Pipeline operator** | Within 48 hrs of monthly PR | 5–15 min | Approve the monthly intake PR; spot-check for obviously bad products (empty labels, duplicate UPCs). |

**Why monthly?** Catalog freshness matters to users, but pulling daily would drown us in duplicates and put real load on the NIH API. Monthly is the right balance.

### Quarterly (deeper work)

| Task | Who | Frequency | Time | What it does |
|---|---|---|---|---|
| Drug-label interaction mining | **Pipeline operator** / **Science reviewer** | Q1, Q2, Q3, Q4 | 30 min + review | Pull new DailyMed-derived drug interactions → propose additions to `ingredient_interaction_rules.json`. |
| Clinical evidence discovery | **Science reviewer** | Quarterly | 1–2 hrs | Search PubMed for new high-quality studies on IQM parents → propose evidence upgrades. |
| ChEMBL bioactivity enrichment | **Pipeline operator** | Quarterly | 30 min | Refresh mechanism-of-action data for IQM entries. |
| Drug class expansion check | **Science reviewer** | Quarterly | 30 min | Review current drug-class taxonomy against real-world med usage trends. |
| IQM alias expansion | **Pipeline operator** | Quarterly | 30–60 min | Add new product-name patterns that currently fall through to unmapped. |
| Botanical enrichment | **Science reviewer** | Quarterly | 30–60 min | New PubMed evidence on botanical ingredients → IQM tier adjustments. |
| Rollback drill | **Pipeline operator** | Quarterly | 15 min | Practice restoring from Supabase snapshot. You don't want to learn how during an emergency. |
| Security audit | **Pipeline operator** | Quarterly | 30 min | Rotate API keys, review GitHub access, check dependency CVEs. |

### Semi-annually / annually

| Task | Who | Frequency | Time | What it does |
|---|---|---|---|---|
| Clinical-copy sweep review | **Dr. Pham** | Every 6 months | 1 full day | Re-read every authored entry — does the voice still match the product philosophy? Are any statements outdated (new IARC classification, new FDA guidance)? |
| Dependency upgrades | **Pipeline operator** | Every 6 months | Half-day | `pip upgrade`, re-run full test suite, fix any breakages. |
| Schema audit | **Pipeline operator** | Annually | Half-day | Review all `_metadata.schema_version` values across data files — are any drifting? Any new fields that should be added to the validator? |
| Regulatory compliance review | **Legal / CSO** | Annually | Half-day | Confirm authored copy still complies with FDA supplement advertising guidance, FTC truth-in-advertising. |

---

## Continuous refresh — the three flywheels

Beyond scheduled tasks, three continuous flywheels keep the pipeline fresh between scheduled ticks.

### Flywheel 1 — Reference-data hot-refresh (Phase 4 unlocks this)

**How it works:**

1. Dr. Pham (or any clinical author) edits a safety_warning / harmful_additive safety_summary / etc. in the web UI.
2. UI opens a PR.
3. PR validator runs → if green, auto-merge to main is enabled.
4. Merge to main triggers `reference-data-change.yml` workflow.
5. Workflow identifies which products reference the changed entry (reverse-index lookup).
6. Targeted rebuild of just those products (not the whole 4,240-product catalog).
7. Re-sync to Supabase.
8. Flutter app fetches updated metadata on next launch → user sees new copy.

**Time from Dr. Pham's save to user seeing it:** ~15–60 minutes.

**What teammates do:** nothing. The flywheel runs itself. Teammates monitor the Slack notifications for failures.

### Flywheel 2 — Monthly catalog intake

**How it works:**

1. First of every month, `monthly-intake.yml` workflow fires.
2. For each enabled category (gummies, capsules, softgels), queries NIH DSLD for new products since last run.
3. Downloads raw JSON → uploads to cloud storage.
4. Opens a PR summarizing the delta.
5. Pipeline operator reviews, approves, merges.
6. Monday morning build picks up the new products.

**Time from NIH publishing a new product to it appearing in our app:** ~5 weeks worst case (right after a monthly intake), ~1 week if you run a manual intake.

**What teammates do:** the pipeline operator spends 5–10 minutes/month approving the monthly PR.

### Flywheel 3 — FDA safety data sync

**How it works:**

1. Every Monday 4am UTC, `fda-safety-sync.yml` workflow fires.
2. Pulls FDA recall database, enforcement reports, CAERS adverse events.
3. Compares to last snapshot → identifies new recalls / new enforcement / new AE signals.
4. Opens a PR: *"FDA sync 2026-05-13: +3 recalls, +1 enforcement action"*.
5. Clinical reviewer eyeballs the new copy (most entries inherit safe boilerplate).
6. Merge → triggers Flywheel 1 (reference data hot-refresh).

**Time from FDA publishing a recall to our users seeing it:** ~5–10 days.

**What teammates do:** clinical reviewer spends ~15 minutes/week on the FDA PR.

---

## What happens if maintenance is skipped

Honest consequences, so the cadence doesn't feel arbitrary:

| Skipped task | 1 week overdue | 1 month overdue | 3 months overdue |
|---|---|---|---|
| FDA recall sync | User might buy a recalled product — medically serious | Legal liability exposure | Regulatory flag; clinical-trust damage |
| Monthly DSLD intake | Missing ~50–200 new products | Noticeable catalog gap | Catalog feels stale to users |
| Clinical-copy review | Probably fine | A few entries drift from evidence base | Dated voice; some entries wrong |
| CAERS refresh | Fine | Some new AE signals missed | Safety score confidence drops |
| Citation content verification | Fine | Fine | Risk of hallucinated citations reaching production |
| Rollback drill | Fine | Fine | When you need to rollback in anger, you won't remember how |

**The critical tasks are weekly FDA sync and monthly DSLD intake.** Everything else has a longer tolerance.

---

## On-call / incident response

When something breaks, the response should be fast and documented.

### Severity tiers

| Severity | Example | Response time | Who |
|---|---|---|---|
| **P0 (production down)** | Supabase offline, app crashes, bad data shipped that misadvises users | <1 hr | Pipeline operator pages CSO |
| **P1 (user-visible data issue)** | A product's score is wrong, a warning is missing | <4 hrs | Pipeline operator |
| **P2 (internal tooling broken)** | Dashboard down, CI failing, monthly intake skipped | <24 hrs | Pipeline operator |
| **P3 (cosmetic / future concern)** | UI typo, doc outdated | Next sprint | Any teammate |

### Incident playbook (for P0 / P1)

1. **Acknowledge** in team Slack within 15 minutes.
2. **Assess** — is this data or code? Rolling back code: `git revert`. Rolling back data: Supabase point-in-time restore (or R2 snapshot restore).
3. **Communicate** — if user-visible, post to any user-facing status page; tell stakeholders.
4. **Fix root cause** — not just the symptom. Open a PR that prevents recurrence.
5. **Write a post-mortem** within 48 hours — what happened, why, what we changed. Store in `docs/incidents/`.

### Post-mortem template

```
# Incident: YYYY-MM-DD [short title]

**Severity:** P0 / P1 / P2 / P3
**Detection:** how we noticed
**Impact:** who was affected, for how long
**Root cause:** one paragraph
**Fix:** PR links
**Follow-ups:** what prevents this next time
```

Non-blaming. The point is learning, not finger-pointing.

---

## Onboarding a new teammate

When you bring someone in, run them through this checklist in their first week.

### Day 1 — Context
- [ ] Read `docs/AUTOMATION_ROADMAP.md` (this doc's companion).
- [ ] Read `docs/PIPELINE_OPERATIONS_README.md`.
- [ ] Read `CLAUDE.md` (project conventions).
- [ ] Log into GitHub, Supabase, Slack. Get repo access.
- [ ] Clone `PharmaGuide_Pipeline` repo.

### Day 2 — Tour
- [ ] Run `python3 -m pytest scripts/tests/ -q` locally. Confirm 3,957 pass.
- [ ] Launch the dashboard locally: `streamlit run scripts/dashboard/app.py`.
- [ ] Click through every view. Ask questions about anything confusing.

### Day 3 — Shadow
- [ ] Pair with pipeline operator through a manual build (`python3 scripts/run_pipeline.py`).
- [ ] Pair through a Supabase sync.
- [ ] Pair through one Dr. Pham PR merge end-to-end.

### Week 2 — Drive
- [ ] Teammate owns next week's FDA safety-sync PR review.
- [ ] Teammate drives one rollback drill (with pipeline operator watching).
- [ ] Teammate ships one documentation fix as a low-stakes first PR.

### Week 4 — Rotate in
- [ ] Teammate owns next monthly DSLD intake approval.
- [ ] Teammate responds to one P2 incident on their own.

After 30 days, teammate is fully integrated.

---

## Red flags that maintenance has slipped

Watch the Clinical Copy dashboard for these signals:

| Signal | What it means | Action |
|---|---|---|
| "Flutter sync stale" on any file | Pipeline schema ahead of Flutter asset | Sync Flutter assets this week |
| Red coverage badge on any file | New entries added, not authored | Queue clinical-author review |
| No builds in the last 7 days | CI broken or nobody's merged | Check GitHub Actions for failures |
| No FDA sync PR in last 10 days | Weekly sync broken | Investigate workflow |
| No monthly intake PR on the 1st | Monthly workflow broken | Run manual intake, fix workflow |
| >3 consecutive PRs failing validator | Validator getting too strict or copy drifting | Investigate |

The dashboard's **Clinical Copy** view (Phase 0 of this automation work already complete) is your at-a-glance health check.

---

## Communication cadence

How the team talks to each other about the pipeline.

### Async (default)

- **Slack channel: `#pharmaguide-pipeline`** — all automated notifications land here (build complete, PR opened, validator failed, FDA sync done).
- **GitHub Discussions** — anything that needs >3 Slack messages becomes a Discussion.
- **Monthly brief email** — pipeline operator writes a 1-paragraph monthly summary to stakeholders (Dr. Pham, legal, investors if applicable): new product count, clinical-copy coverage, any incidents, next month's focus.

### Sync (as needed)

- **Weekly pipeline sync** (optional once you have 2+ people) — 15 min, Monday, review last week's builds + upcoming PRs.
- **Monthly clinical review** — 30 min, Dr. Pham + pipeline operator + anyone else reviewing — review backlog, discuss edge cases.
- **Quarterly strategy review** — 1 hour, review the automation roadmap, adjust priorities.

Don't meet just to meet. Default to async; promote to sync only when async is failing.

---

## What's not in this doc (but might be soon)

As the pipeline and team grow, add sections for:

- **SLAs** to external consumers (Flutter app, third-party integrations).
- **Data retention policy** — how long we keep raw JSON, old Supabase snapshots, old product versions.
- **User-feedback loop** — how user-reported issues flow back into the pipeline.
- **Growth planning** — when do we add a paid tier, hire a full-time ops person, etc.

If you find yourself answering the same question twice in Slack, add it here.

---

## Current state (as of 2026-04-18)

- **Pipeline operator:** Sean
- **Clinical author:** Dr. Pham (round 1 complete + round 2a/b-full complete across 6 data files)
- **Cadence today:** manual, ad-hoc
- **Cadence target:** Phase 1 automation deployed within 1 month; Phase 3 monthly automation within 3 months
- **Total data files clinically reviewed:** 6 of 6 (medication_depletions, banned_recalled_ingredients, ingredient_interaction_rules, harmful_additives, synergy_cluster, manufacturer_violations)
- **Automation level:** ~5% (only test suite runs in CI today)
- **Automation target in 6 months:** ~80% (Phase 5 reached)

Update this state section quarterly.
