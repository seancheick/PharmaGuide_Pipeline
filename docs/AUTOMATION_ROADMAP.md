# PharmaGuide — Automation & Collaboration Roadmap

**Audience:** Sean (technical) + anyone you bring in (non-technical).
**Goal:** Move from "everything runs on Sean's laptop" → "fully automated, multi-person, self-refreshing pipeline."
**Timeline:** 6 months end-to-end, phased. Each phase is a real deliverable on its own — you can stop at any phase if business needs shift.
**Bootstrap constraint:** every recommendation has a free-tier option. Paid upgrades are flagged explicitly.

This document reads top-to-bottom. Each phase explains what it is in plain English, why it matters, and the step-by-step work to get there.

---

## How to read this document

Every phase has the same structure:

1. **What it is** — plain English, non-technical.
2. **Why it matters** — the specific problem it solves.
3. **How to do it** — concrete steps, in order.
4. **Free option + paid upgrade** — what to use while bootstrapping, what to upgrade to when the business grows.
5. **Definition of done** — how you know the phase is finished.
6. **Estimated effort** — realistic range, assumes part-time work.

Phase numbers are roughly sequential, but a few (like Phase 2 and 3) can run in parallel once Phase 1 is in place.

---

## Stage 0 — Where you are today (audit)

Before any new work, it helps to be honest about what exists.

### What already works

- **DSLD intake scripts** (`scripts/dsld_api_client.py`, `scripts/dsld_api_sync.py`) — you can fetch from NIH DSLD by brand, query, filter, or supplement form code (gummies=`e0176`, capsules=`e0159`, softgels=`e0161`, etc.). A state file tracks what's been seen so delta pulls work.
- **3-stage pipeline** (`run_pipeline.py` → clean → enrich → score). Deterministic, testable, 3,957 tests passing.
- **Final DB build** (`build_final_db.py`) merges all brands into a single SQLite + detail blobs + manifest.
- **Supabase sync** (`sync_to_supabase.py`) pushes the built DB to your hosted database.
- **Validation gate** (`validate_safety_copy.py` `--strict`) — catches authoring mistakes before shipping.
- **Dashboard** (`scripts/dashboard/`) — Streamlit UI for inspecting builds, spotting staleness, Dr. Pham's clinical copy coverage.
- **Git + GitHub** — pipeline repo is at `github.com/seancheick/PharmaGuide_Pipeline`.

### What doesn't work for collaboration

1. **Raw DSLD JSON lives on your laptop.** If someone else wants to add brands they'd have to pull gigabytes of data from you first.
2. **Pipeline runs locally only.** You are the bottleneck — no one else can trigger a build.
3. **No scheduled automation.** New NIH DSLD products appear weekly; nobody pulls them until you manually do it.
4. **Dr. Pham's review loop depends on you.** She sends files over Slack/email; you validate, commit, push.
5. **No "reference data changed → rebuild" signal.** Change a safety warning, the existing blobs still carry the old text until you remember to rebuild + resync.
6. **Flutter app updates are manual.** Push to Supabase, hope the app picks it up.

### The 3 separable problems

Everything below untangles these three:

| Problem | Current state | Target state |
|---|---|---|
| **Data intake** (new products from NIH) | Manual, laptop | Scheduled, cloud |
| **Pipeline execution** (clean/enrich/score/build) | Local laptop | GitHub Actions or cloud runner |
| **Clinical-copy authoring** (Dr. Pham's work) | Files over Slack | Web UI → PR → auto-validate |

---

## Phase 1 — Pipeline runs without your laptop

**Timeline:** 2–3 weeks part-time.
**Cost:** $0/month (free tier).
**Unblocks:** every other phase. Start here.

### What it is

Right now the pipeline runs on your Mac. In Phase 1 we lift it into **GitHub Actions** — the same place your tests already run — and move the product data to **cloud storage** so anyone with access can trigger a build.

After Phase 1, anyone (you, a teammate, a future hire) can click "Run workflow" in GitHub, and the full pipeline executes in the cloud. No laptop required.

### Why it matters

Three direct wins:

1. **You're no longer the bottleneck.** A teammate could run a full build while you're on vacation.
2. **Builds are reproducible.** No more "works on my Mac" bugs — every build runs in an identical clean environment.
3. **Audit trail.** Every build leaves a log in GitHub Actions showing what ran, when, and who triggered it.

### How to do it

**Step 1.1 — Move raw DSLD JSON to cloud storage.**

Today: `scripts/products/output_{Brand}/cleaned/*.json` lives on your laptop.
Tomorrow: it lives in a cloud bucket (Supabase Storage, Cloudflare R2, or Backblaze B2 — all free tier).

Pick one storage provider (see **Free options** below). Upload each brand folder as `s3://pharmaguide-pipeline/raw/{Brand}/*.json`. Then update `run_pipeline.py` to pull from the bucket if a `--remote` flag is set.

**Step 1.2 — Write a GitHub Actions workflow.**

Create `.github/workflows/build-db.yml`. It should:
- Run on: `workflow_dispatch` (manual button) + weekly cron (`0 8 * * 1` = Mondays 8am UTC).
- Install Python 3.13, dependencies.
- Pull raw JSON from bucket.
- Run `run_pipeline.py` on all brands.
- Run `build_final_db.py`.
- Run `validate_safety_copy.py --strict` (release gate — fail the build if it fails).
- Upload final DB to Supabase via `sync_to_supabase.py`.
- Post a Slack notification (optional, free via webhook).

**Step 1.3 — Brand config file.**

Create `config/brands.json`:

```json
{
  "brands": [
    { "name": "Nature_Made", "enabled": true },
    { "name": "CVS", "enabled": true },
    { "name": "Garden_of_life", "enabled": true }
  ]
}
```

The workflow iterates this list. Adding a new brand = one-line PR.

**Step 1.4 — Secrets.**

GitHub repo settings → Secrets → add:
- `DSLD_API_KEY` — NIH DSLD API key (free from NIH)
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`
- Storage credentials (Supabase / R2 / B2 keys)
- `PUBMED_API_KEY`, `UMLS_API_KEY`, `OPENFDA_API_KEY`

All referenced in the workflow as `${{ secrets.DSLD_API_KEY }}`.

### Free options

| Tool | Free tier | Paid upgrade |
|---|---|---|
| **Cloud storage** | **Supabase Storage** (1 GB free, already connected to you). Alternate: Cloudflare R2 (10 GB free + zero egress cost — strongest free tier on the market). Backblaze B2 (10 GB free). | Supabase Pro ($25/mo, 100 GB). R2 after 10 GB is ~$0.015/GB. |
| **CI/CD** | **GitHub Actions** (2,000 free minutes/month for private repos; unlimited for public). | GitHub Pro ($4/user/mo, 3,000 minutes). |
| **Secrets mgmt** | **GitHub Secrets** (free). | Doppler, 1Password (paid). |
| **Notifications** | **Slack incoming webhook** (free). **Discord webhook** (free). | PagerDuty ($25/user/mo). |

**My recommendation for Phase 1:** Cloudflare R2 for storage (best free tier, no egress fees when Flutter eventually pulls from it) + GitHub Actions + Supabase for the final DB.

### Definition of done

- Push a commit to main → workflow runs → final DB lands in Supabase → you get a Slack ping within 30 minutes.
- A teammate (with GitHub access) can click "Run workflow" and produce the same result.
- Your laptop can be powered off for a week and the pipeline still runs Mondays.

### Effort

**15–25 hours** part-time. The DSLD intake is already built, so this is mostly YAML + storage glue.

---

## Phase 2 — Dr. Pham (and any reviewer) edits clinical copy without git

**Timeline:** 3–4 weeks part-time.
**Cost:** $0/month.
**Can run in parallel with Phase 3.**

### What it is

Today Dr. Pham edits `_Reviewed.json` files locally and sends them to you. In Phase 2 we give her a **web-based editor** (extension of the Streamlit dashboard you already built) where she can:

1. See every entry that needs authoring (coverage page you already have)
2. Click an entry, see the authored fields as an editable form
3. Save → the UI **opens a GitHub pull request** with her changes
4. You (or any reviewer) approve the PR → the validator runs automatically → merge

She never touches git, files, or Slack. You never manually sync files.

### Why it matters

- **Her round time drops from days to hours.** No "wait for Sean to sync" cycle.
- **Zero human-error risk.** Validator runs on every PR; no PR can merge if it breaks the tone contract.
- **Audit trail.** Every change is a PR with her name, date, diff. Legal/regulatory-review-ready.
- **Works for future reviewers too.** Second clinical reviewer? Add them as a collaborator — same UI.

### How to do it

**Step 2.1 — Extend the Clinical Copy dashboard with edit mode.**

The dashboard already shows coverage and a random spot-check picker. Add:

- A "Edit mode" toggle (password-gated).
- On any entry, an "Edit" button that opens a form pre-filled with current values.
- A "Save to PR" button that:
  1. Clones the repo (or uses GitHub API)
  2. Creates a branch `clinical-review/{reviewer}-{timestamp}`
  3. Commits the change
  4. Opens a PR against main
  5. Shows the reviewer the PR URL

**Step 2.2 — Add strict-validator PR check.**

Create `.github/workflows/validate-pr.yml`. On every PR that touches `scripts/data/*.json`:
- Run `python3 scripts/validate_safety_copy.py --strict`
- Run `python3 -m pytest scripts/tests/ -q`
- Fail the PR if either fails.

GitHub shows the status check inline on the PR — can't merge red.

**Step 2.3 — Host the dashboard somewhere Dr. Pham can reach.**

Three options:

| Option | Setup | Free tier |
|---|---|---|
| **Streamlit Cloud** | Connect GitHub repo, one-click deploy. | Yes — unlimited apps on private repos for teams, rate-limited on community. |
| **Render / Railway / Fly.io** | Docker deploy from repo. | Yes — free tier sufficient for small team. |
| **Cloudflare Tunnel** (self-hosted) | Run Streamlit on your Mac, expose via Cloudflare tunnel. | Yes — $0 but your Mac has to be on. |

**Recommendation:** Streamlit Cloud for the dashboard. Free, private, GitHub-integrated. Deploys on every push.

**Step 2.4 — Role-based edit permissions.**

Dr. Pham can edit authored fields (`alert_headline`, `alert_body`, etc.) but should not edit `severity`, `mechanism`, `evidence_level`, `PMIDs`. Lock those at the form layer — the schema stays editable, but the form only exposes authored fields.

### Free options

| Tool | Free tier | Notes |
|---|---|---|
| **Streamlit Cloud** | Private apps free for small teams | Native GitHub integration |
| **GitHub API** (for programmatic PRs) | Free | Use `PyGithub` library |
| **GitHub Actions PR checks** | Included in Actions free minutes | Standard |

### Definition of done

- Dr. Pham logs into the dashboard from her laptop.
- She edits a harmful_additives entry, saves.
- A PR appears in GitHub with her change.
- Validator auto-runs, goes green.
- You (or a CSO) click approve + merge.
- Phase 1 workflow rebuilds the DB on the new content.
- Dr. Pham's change is live in Supabase within 1 hour of her clicking Save.

### Effort

**25–40 hours** part-time. The dashboard exists; this is form + PR-opener scaffolding.

---

## Phase 3 — Scheduled intake + category pulls + monthly delta

**Timeline:** 2 months part-time.
**Cost:** $0/month initially.
**Depends on Phase 1.**

### What it is

You said the target: "pull by category — gummies, capsules, softgels — each as its own category, once a month delta only." Today `dsld_api_sync.py` can do the pulls; this phase wraps scheduling, state tracking, and auto-PR around it.

After Phase 3:
- Every month, a scheduled job queries NIH DSLD by category (gummies, capsules, softgels, etc.).
- It compares to the last snapshot (state file from `dsld_api_sync.py`).
- New products → auto-download raw JSON → upload to storage → open a PR: *"Add 47 new gummy products (delta vs last month)"*.
- You or a teammate review the PR → approve → Phase 1 rebuild kicks in → new products are live.

### Why it matters

- **Catalog grows automatically.** You stop being the gate on "did we pull the new products?"
- **Category-first scaling.** You can onboard new categories one at a time (start with gummies, add capsules next month).
- **Delta-only keeps costs + compute low.** You don't re-process 4,000 unchanged products just because one new one dropped.

### How to do it

**Step 3.1 — Category config.**

Create `config/categories.json`:

```json
{
  "categories": [
    {
      "slug": "gummies",
      "dsld_form_code": "e0176",
      "enabled": true,
      "monthly_cap": 500,
      "last_sync": "2026-04-18T00:00:00Z",
      "last_dsld_ids_seen": 12345
    },
    {
      "slug": "capsules",
      "dsld_form_code": "e0159",
      "enabled": true,
      "monthly_cap": 500
    }
  ]
}
```

**Step 3.2 — Monthly intake workflow.**

Create `.github/workflows/monthly-intake.yml` running on cron `0 0 1 * *` (midnight, first of month). It:

1. For each enabled category:
   - Calls `python3 scripts/dsld_api_sync.py filter --supplement-form {code} --status 1 --limit {cap}`
   - Compares returned IDs vs `last_dsld_ids_seen` in state file → new IDs = delta
   - Downloads raw JSON for new IDs into storage bucket
2. Opens a PR titled *"Monthly intake YYYY-MM: +X gummies, +Y capsules"* with:
   - New raw JSON file paths
   - Updated state file
3. You / reviewer approve → merge → triggers Phase 1 rebuild.

**Step 3.3 — Safety caps (don't eat the NIH API).**

Per-category per-month limit (e.g., 500 new products/category/month). If DSLD has 2,000 new gummies, the workflow takes the first 500 and flags the rest for manual review. Keeps the pipeline from drowning in one bad month.

**Step 3.4 — Deduplication across categories.**

Same product can appear under two form codes (some gummies also count as softgels). Use DSLD `id` as the dedup key; any product already in the catalog gets skipped.

**Step 3.5 — Change detection (not just new products).**

DSLD products get updated (new UPC, reformulation, label change). Extend the state file to track a hash of each label's core fields. On intake:
- New ID → add.
- Existing ID with different hash → flag as "updated" → re-enrich + re-score → open separate PR.
- Unchanged → skip.

### Free options

| Tool | Free tier | Notes |
|---|---|---|
| **GitHub Actions cron** | Included | Runs reliably once a day minimum |
| **NIH DSLD API** | Free, public, no key limit for reasonable use | Already wired in `dsld_api_client.py` |

### Definition of done

- First of the month rolls around, a workflow runs.
- By 9am that day a PR appears in GitHub titled *"Monthly intake 2026-05: +42 gummies, +18 capsules, +3 updated products"*.
- You approve → Phase 1 rebuilds → new products live in the app by end of day.
- You spend ~5 minutes per month on intake oversight instead of an afternoon.

### Effort

**40–60 hours** over 2 months. Category + delta logic is built; this is state tracking, scheduling, PR automation.

---

## Phase 4 — Reference-data hot-refresh

**Timeline:** 2–3 months part-time.
**Cost:** $0/month.
**Depends on Phase 1.**

### What it is

You asked: *"If we change the wording on a harmful additive, users should get the updated version."*

Today, changing `scripts/data/harmful_additives.json` doesn't automatically propagate to the app — you have to rebuild + resync. Phase 4 makes this automatic.

After Phase 4: any change to any reference file (`scripts/data/*.json`) triggers a smart rebuild of only the affected products, resyncs to Supabase, and the Flutter app picks it up on next launch.

### Why it matters

- **Dr. Pham fixes a typo → user sees the fix same day.** No "wait for next monthly release."
- **New banned substance added → immediately disqualifies affected products.** Safety-critical.
- **Copy refinements compound.** You can iterate authored copy weekly without friction.
- **Efficient.** Change one entry → rebuild 10 products, not 4,000.

### How to do it

**Step 4.1 — Dependency graph.**

For each reference file, track which product fields it influences:

```
harmful_additives.json  →  warnings_profile_gated (type=harmful_additive)
banned_recalled_ingredients.json  →  warnings (type=banned/recalled), has_banned_substance
synergy_cluster.json  →  synergy_detail
manufacturer_violations.json  →  manufacturer_detail.violations, brand_trust score
medication_depletions.json  →  depletion_alerts (Flutter-side feature)
ingredient_interaction_rules.json  →  warnings_profile_gated (type=interaction)
```

Store this as `config/rebuild_dependencies.json`.

**Step 4.2 — Affected-products index.**

Every product blob already includes the reference-data identifiers it matched (e.g., which harmful_additive IDs hit). Build a reverse index: *"harmful_additive ADD_ASPARTAME is referenced by products X, Y, Z."* Store in Supabase as `reference_product_refs` table, populated on each build.

**Step 4.3 — Change-detection workflow.**

Create `.github/workflows/reference-data-change.yml` triggered on PR merge to main that touches `scripts/data/*.json`:

1. Diff the change against previous commit.
2. For each changed entry, query the affected-products index.
3. If <50 products affected → targeted rebuild (re-enrich + re-score + re-build-blobs for just those products, patch the Supabase table).
4. If ≥50 products affected → full rebuild (Phase 1 workflow).
5. Post a Slack note: *"Copy change to harmful_additives:ADD_ASPARTAME rebuilt 12 products. Live in Supabase."*

**Step 4.4 — Flutter cache invalidation.**

The Flutter app caches reference data locally for offline mode. On first app launch each day, fetch the `_metadata.schema_version` from Supabase → compare to cached version → if mismatch, re-download. Easy to add with the `http` package Flutter already uses.

**Step 4.5 — Rollback mechanism.**

Keep the previous Supabase DB snapshot for 30 days. If a bad change ships, one-click revert restores the prior state. Supabase free tier supports point-in-time restore on paid plans; on free tier, just snapshot the DB file to cloud storage before every sync.

### Free options

| Tool | Free tier | Notes |
|---|---|---|
| **Supabase snapshots** | Point-in-time restore is Pro-only ($25/mo) | Workaround: store nightly DB dump in R2 / Supabase Storage |
| **Flutter cache invalidation** | Free | Simple client-side schema check |

### Definition of done

- Dr. Pham edits an aspartame safety_summary in the dashboard.
- PR opens, validator passes, you approve + merge.
- Within 5 minutes, the 8 products containing aspartame in their blobs get re-emitted with the new copy.
- A user opens the Flutter app the next morning — it fetches updated reference data on launch and now shows the new string.
- Total human time involved: ~30 seconds of click-approve.

### Effort

**60–100 hours** over 2-3 months. This is the most engineering-heavy phase; it introduces real incremental-update logic. Don't rush it.

---

## Phase 5 — Full automation & observability

**Timeline:** 6 months from start, ongoing.
**Cost:** $0-$25/month.

### What it is

Phases 1–4 are the backbone. Phase 5 wraps them in production-grade polish so you can trust the pipeline to run unattended.

- **End-to-end observability.** Grafana/Supabase dashboards showing: build frequency, product count growth, clinical-copy coverage over time, Flutter fetch latency, DB size.
- **Alerting.** If a monthly intake fails, someone gets paged. If a validator starts failing for 3 consecutive PRs, you get a ping.
- **Audit trail.** Who authored what, when, approved by whom. Export as CSV for regulatory review.
- **Rollback drills.** Practice restoring from snapshot quarterly.
- **Staging environment.** A second Supabase project mirrors production. Every PR auto-deploys to staging first; Flutter dev builds read staging.
- **Cost dashboard.** Track storage + compute + API costs.

### Why it matters

You don't need this until you have real users. When you do, the compound savings are huge:
- You see problems in the dashboard before users do.
- You can prove (to auditors, to Dr. Pham, to investors) what happened when.
- Recovering from a bad release is 5 minutes instead of a day.

### How to do it

**Step 5.1** — Supabase has built-in logs + metrics. Connect Grafana Cloud (free tier) for richer visualization.
**Step 5.2** — Slack/Discord alerting from GitHub Actions failures (free webhooks).
**Step 5.3** — Append-only `audit_log` table in Supabase — every PR merge writes a row.
**Step 5.4** — Second Supabase project for staging (free tier allows 2 projects).
**Step 5.5** — Monthly calendar reminder to practice a rollback (no tooling needed, just discipline).

### Definition of done

You take a week off. Nothing pages you. You come back, check the dashboard, everything shipped on time.

### Effort

**20–40 hours** spread over months, integrated as you go.

---

## Free tool stack — consolidated

| Need | Free option (recommend) | When to upgrade |
|---|---|---|
| **Git hosting** | GitHub (unlimited private repos) | Never — free tier is great |
| **CI/CD** | GitHub Actions (2,000 min/mo private; unlimited public) | When you exceed minutes (~$4/mo) |
| **Cloud storage** | **Cloudflare R2** (10 GB, zero egress) | After 10 GB ($0.015/GB) |
| **Database + realtime** | **Supabase** free tier (500 MB DB, 1 GB file storage) | When DB >500 MB → Pro ($25/mo) |
| **Edge compute** | Supabase Edge Functions (free tier) / Cloudflare Workers (free tier, 100k req/day) | Paid tier unlikely needed early |
| **Dashboard hosting** | Streamlit Cloud (free for private with team) / Cloudflare Pages (free) | Never for solo |
| **Secrets** | GitHub Secrets (free) | Never |
| **Notifications** | Slack/Discord webhooks (free) | PagerDuty when >10 people |
| **Monitoring** | Grafana Cloud free (10 k metric series) | Paid when >10k |
| **Error tracking** | Sentry free tier (5,000 events/mo) | $26/mo at scale |
| **Uptime monitoring** | UptimeRobot (free, 50 monitors) | Never — free is great |
| **APIs** | NIH DSLD (free, public), PubMed (free with key), openFDA (free with key), UMLS (free with registration) | None needed |

**Minimum monthly cost at scale (~10k users, 10k products):** $0–$25 (just Supabase Pro if you outgrow the free DB tier). Everything else stays free for a long time.

---

## What to do this week — concrete starter

Start tiny. One commit. No phase commitment.

### Day 1 (2 hours)

- Create `config/brands.json` listing your 15 current brands (just copy the folder names).
- Create `config/categories.json` with the 3 form codes you care about (gummies, capsules, softgels) + `"enabled": false` on all so nothing runs yet.
- Commit + push.

That's it. Tomorrow you already have a config file, which is the scaffolding for phases 1 and 3.

### Day 2–3 (3 hours)

- Sign up for Cloudflare R2 (free) and create a bucket `pharmaguide-pipeline`.
- Upload one brand's raw JSON to `r2://pharmaguide-pipeline/raw/Nature_Made/`.
- Manually test: download it back, run pipeline, confirm output matches local run.

### Day 4–5 (4 hours)

- Draft `.github/workflows/build-db.yml` (I can write this for you when you're ready — say the word).
- Start with a single brand (Nature_Made) in the workflow. Don't try all 15 at once.
- Merge → watch the Actions tab → verify the DB lands in Supabase.

### Week 2

- Scale the workflow to all 15 brands.
- Add a Slack webhook for completion notifications.
- At this point you've finished Phase 1 for practical purposes.

---

## Summary roadmap at a glance

| Phase | Deliverable | Time | Cost | Depends on |
|---|---|---|---|---|
| **0** | Stage 0 audit (read this doc, understand current state) | 1 hour | $0 | — |
| **1** | Pipeline runs in GitHub Actions from cloud storage | 2–3 weeks | $0 | — |
| **2** | Dr. Pham edits clinical copy via web UI → PR | 3–4 weeks | $0 | Phase 1 (recommended) |
| **3** | Monthly scheduled DSLD intake by category with delta detection | 2 months | $0 | Phase 1 |
| **4** | Reference-data changes auto-propagate to affected products + Flutter | 2–3 months | $0 | Phase 1 |
| **5** | Full observability, alerting, audit trail, staging | ongoing | $0–$25/mo | Phases 1–4 |

**6 months from today:** a teammate adds a new brand by making a one-line PR; intake runs monthly without you; Dr. Pham's typo fix reaches users within an hour of her saving; you can take a week off and nothing breaks.

---

## My honest recommendation

**Do Phase 1 now. Pause. See if the business needs justify Phase 2/3.**

Phase 1 alone solves 80% of your collaboration pain. The others are polish layers that matter once you have real multi-person workflows and real user volume. Don't build complexity you don't need yet.

When you're ready to start Phase 1, I can:
- Draft `.github/workflows/build-db.yml` based on your actual `run_pipeline.py` signature.
- Write the `scripts/storage_client.py` abstraction so the pipeline can read from R2 or Supabase Storage interchangeably.
- Migrate one brand's raw JSON to the bucket as a proof-of-concept.

Just say when.
