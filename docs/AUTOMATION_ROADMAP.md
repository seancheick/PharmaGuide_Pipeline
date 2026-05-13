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

### The 4 separable problems

Everything below untangles these four:

| Problem | Current state | Target state |
|---|---|---|
| **Data intake** (new products from NIH) | Manual, laptop | Scheduled, cloud |
| **Pipeline execution** (clean/enrich/score/build) | Local laptop | GitHub Actions or cloud runner |
| **Clinical-copy authoring** (Dr. Pham's work) | Files over Slack | Web UI → PR → auto-validate |
| **Safety alerts** (FDA recalls/bans, same-day) | Not built | 15-min poller + Supabase Realtime + FCM push |

### Scale trajectory

| Stage | Product count | What ships | Storage model | Monetization |
|---|---|---|---|---|
| **Beta** (Month 0-6) | 10k popular brands | Hand-curated top brands | Full blob bundle in app OR Supabase on-demand (either works at this size) | **Free for everyone** — acquisition phase, no paywall |
| **V1 post-beta** (Month 6-12) | ~50k top categories | Gummies, capsules, softgels, then liquids, etc. | Reference data in app; **product blobs fetched on-demand from Supabase** | **Pro tier activates** — free tier becomes limited; Pro unlocks full features |
| **Full** (Month 12+) | 250k (all DSLD) | Whole DSLD catalog | Reference data in app (<10 MB); all product blobs on Supabase; aggressive caching + prefetch | Pro tier enforced across all Phase 4.5 gates |

### Monetization timeline & free-tier limits

**Month 0–6 (beta):** everything free. No gating. Goal = acquire users, validate product-market fit, learn which features users actually use. Telemetry runs throughout so we have usage data to inform the free/pro line.

**Month 6+ (Pro paywall activates):** the free tier becomes limited. Specific limits (to be calibrated from beta telemetry, but planned scope):

| Feature | Free tier (post-beta) | Pro tier |
|---|---|---|
| Daily scans | Limited (e.g., 10/day) | Unlimited |
| Stack size | Limited (e.g., 5 products) | Unlimited |
| Stack-level interaction checking | Basic (pairwise, top severity only) | Full (multi-way, all severities, timing guidance) |
| Offline product DB | Top 50k (Tier 1 shard only) | Top 150k (Tier 2 post-install pack) |
| Detail blob cache | ~50 products rolling window | Unlimited |
| FDA CRITICAL push alerts | **Always on (never gated)** | Always on |
| FDA HIGH/CATALOG push alerts | Not included | Included |
| Alert history / export | Current session only | Full history, CSV/PDF export |
| Depletion tracking | View only | Monitoring tips, food-source suggestions |
| Family sharing | Single user | Up to 5 family members |

**What gates get enforced:** per-feature counters on the client, validated server-side on sensitive calls (detail blob fetches, Tier 2 pack download signing).

**What never gates:** CRITICAL safety alerts (non-negotiable), basic verdict/score/safe-not-safe (the core trust signal).

### Infrastructure consequences

The paywall activation in Month 6 means we need to build two things during beta that **don't gate anything yet** but capture the data and enforce the plumbing:

1. **Usage telemetry from Phase 1 onwards.** Track: scans/day/user, stack size, cached-blob count, feature-area activity. Stored in Supabase `usage_events` table. Enables calibrating the free-tier limits from real data before Month 6, not from guessing.

2. **Tier-aware client scaffolding.** Flutter checks `currentUser.tier` before every gate-able action, even during beta when `tier` is always 'pro'. This way, flipping the paywall switch at Month 6 is a one-line change, not a refactor.

Both are small additions to existing phase work, not their own phases. Documented here so we don't forget.

**Confirmed architecture decision:** at V1+, Flutter **does not** ship with every product blob in its offline bundle. Only the reference-data layer (banned, harmful additives, interactions, depletions, synergy clusters, violations) stays on-device. Product detail blobs fetch from Supabase on-demand when a user scans or searches. This keeps the app install size flat as the catalog grows from 10k → 250k.

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

## Phase 1.5 — Safety Alert Short Path (same-day FDA recall / ban alerts)

**Timeline:** 2–3 weeks part-time.
**Cost:** $0/month.
**Depends on Phase 1 (needs Supabase connection in CI).**
**Critical for shipping at all — do this before public beta.**

### What it is

A dedicated, sub-hour lane for FDA recalls and emergency safety alerts that **bypasses the full pipeline rebuild.** When the FDA publishes a Class I recall at 9am, a user with that product in their stack gets a push notification within minutes — not the next monthly build.

The existing pipeline is the *slow lane* (accurate, thorough, rebuilt monthly). Phase 1.5 builds the *fast lane* (opinionated, conservative, live in minutes) alongside it. Both stay in sync because they share the same `banned_recalled_ingredients.json` source of truth; the fast lane just reaches users a week earlier.

### Why it matters

- **User safety.** If a user takes a supplement that was recalled yesterday morning, a weekly build is a clinical failure. Minutes matter.
- **Regulatory posture.** Demonstrating a same-day safety-alert path is a differentiator versus apps that rebuild monthly. It's also defensive against liability.
- **Trust.** Users who get a "your supplement was just recalled — stop using it" push build long-term confidence in the app's safety signal.
- **Scales for free.** The whole architecture below runs on free-tier Cloudflare + Supabase + FCM.

### Three-tier alert model

Not every alert needs a push notification. Tier the response to the severity:

| Tier | Triggers | UX | Latency target |
|---|---|---|---|
| **1 — CRITICAL** | FDA Class I recall, DEA Schedule I substance, undeclared controlled drug, emergency use authorization withdrawal | Push notification + red banner on app open | <15 min FDA publish → user |
| **2 — HIGH** | Class II/III recall, FDA warning letter, CAERS adverse-event cluster, manufacturer criminal prosecution | In-app banner on next open, no push | <4 hours |
| **3 — CATALOG** | New products, copy refinements, ingredient metadata, non-urgent reference data | Silent refresh on next app launch | <24 hours |

### How it works — architecture

```
FDA openFDA API + FDA RSS              NIH DSLD updates
         │                                     │
         ▼                                     ▼
Cloudflare Cron Worker                 Weekly/monthly
(polls every 15 min, free)             intake (Phase 3)
         │                                     │
         ▼                                     ▼
  Delta detection                       Full pipeline rebuild
  (new recalls since last poll)
         │
         ▼
Supabase Edge Function:                Supabase safety_alerts table
  1. Write row to safety_alerts        (new row per alert, tier column)
     with auto-drafted conservative            │
     copy + tier classification                │
  2. Match against reference DB                ▼
     to tag affected products           Flutter clients subscribe via
         │                              Supabase Realtime (websocket)
         ▼                                     │
  Open PR: "FDA alert YYYY-MM-DD:             │
  +X Tier-1 recalls. Dr. Pham to              ▼
  refine copy within 24hrs"            Client-side stack match
                                       (product in user's stack?)
  (Dr. Pham refines within 24-48hrs           │
   → same row updates in Supabase              │
   → clients pull refined copy on              ▼
   next Realtime update)                 ─ Tier 1: FCM push
                                         ─ Tier 2: banner next open
                                         ─ Tier 3: silent refresh
```

### The critical concept — **auto-drafted conservative copy**

Dr. Pham cannot be in the loop for the first-minute alert; she's asleep, the FDA doesn't wait. But we can't show users unstructured raw FDA text either (it's clinician-voiced, often alarmist, sometimes confusing).

**Solution:** Supabase Edge Function auto-generates a conservative fallback copy that ships with the alert immediately:

```
FDA published: "Voluntary Class I Recall of [Brand X Product Y], Lot #12345,
due to undeclared sibutramine, a prescription drug removed from the US market."

Auto-drafted safety_warning (Tier 1 copy, ships in <15 min):
"FDA recall: this product was recalled due to an undeclared prescription drug.
Stop using any bottles you have and talk to your doctor if you've been taking it.
Dr. Pham will post a fuller clinical note within 24 hours."

safety_warning_one_liner:
"FDA Class I recall — stop use immediately."
```

The auto-draft follows a strict template (no SCREAM words, no encyclopedic openers, standard Dr. Pham tone rules) and is generated by a small rules engine, not an LLM. Deterministic, testable, clinically safe.

Dr. Pham refines the copy within 24–48 hours (Phase 2 web editor makes this one click); users get the refined version on the next app open.

### Privacy-preserving stack match

The server never sees which products a user has in their stack. Architecture:

1. Server broadcasts **every** safety alert to **all** subscribed clients.
2. Each Flutter client checks locally: "does this alert affect any product in my stack?"
3. Only matching clients fire the push notification.

At 100k users with ~10 alerts/month, each client processes ~10 websocket messages/month. Bandwidth cost per user: negligible. Privacy: complete — we never know which users got alerted.

### How to do it

**Step 1.5.1 — Supabase schema:**

```sql
CREATE TABLE safety_alerts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tier          TEXT NOT NULL CHECK (tier IN ('CRITICAL', 'HIGH', 'CATALOG')),
  source        TEXT NOT NULL,            -- 'openfda_food', 'openfda_drug', 'fda_rss', 'dea'
  source_id     TEXT NOT NULL,            -- FDA recall number / enforcement ID
  published_at  TIMESTAMPTZ NOT NULL,
  ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  canonical_ids JSONB NOT NULL,           -- array of banned_recalled_ingredients.json IDs this maps to
  upc_codes     JSONB,                    -- UPC/SKU list for targeted match
  brand_match   TEXT,                     -- brand name for alternate match
  product_match TEXT,                     -- product name for alternate match
  safety_warning TEXT NOT NULL,           -- auto-drafted initially, Dr. Pham refines
  safety_warning_one_liner TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'auto_drafted' CHECK (status IN ('auto_drafted', 'reviewed', 'superseded')),
  refined_by    TEXT,                     -- username of clinical reviewer
  refined_at    TIMESTAMPTZ
);

CREATE INDEX safety_alerts_published_idx ON safety_alerts (published_at DESC);
CREATE INDEX safety_alerts_canonical_ids_idx ON safety_alerts USING GIN (canonical_ids);
```

**Step 1.5.2 — Cloudflare Cron Worker** (`workers/safety-alert-poller.ts`):

- Runs every 15 minutes.
- Hits `https://api.fda.gov/food/enforcement.json?search=report_date:[last_poll_ts TO NOW]`.
- Parses new recalls, deduplicates against `safety_alerts` table.
- For each new recall, calls Supabase Edge Function to insert + draft copy.

**Step 1.5.3 — Supabase Edge Function** (`supabase/functions/draft-safety-alert/index.ts`):

- Input: raw FDA payload.
- Classifies tier (Class I → CRITICAL; Class II/III → HIGH; anything else → CATALOG).
- Matches against `banned_recalled_ingredients.json` canonical IDs (product name / UPC / ingredient).
- Generates conservative safety_warning + one_liner using a template engine.
- Inserts row into `safety_alerts`.
- Opens a GitHub PR (via GitHub API) proposing to add this to `banned_recalled_ingredients.json` with Dr. Pham's editorial queue.

**Step 1.5.4 — Flutter Realtime subscription:**

- On app launch, subscribe to `safety_alerts` table via Supabase Realtime.
- Cache all alerts locally.
- Match against user's stack (local only).
- For Tier 1 matches: `FirebaseMessaging.instance.showNotification(...)`.
- For Tier 2/3 matches: banner badge on main nav.

**Step 1.5.5 — Dr. Pham refinement flow:**

- Dr. Pham visits `#safety-alerts-queue` in the dashboard.
- Sees all auto-drafted alerts awaiting refinement.
- Edits the safety_warning in-line (inherits the Phase 2 web editor pattern).
- Save → updates the Supabase row + marks `status='reviewed'` → Realtime pushes update to clients.

**Step 1.5.6 — Push notifications via Firebase:**

- Flutter already supports FCM; add the Tier-1 match trigger.
- Notification body: `safety_warning_one_liner`.
- Tap → opens to the product detail in the app.

### Free options

| Tool | Free tier | Notes |
|---|---|---|
| **Cloudflare Workers** | 100k requests/day | 15-min polling = 96 requests/day, 99.9% headroom |
| **Supabase Realtime** | Unlimited channels, free tier | Already in Supabase setup |
| **Supabase Edge Functions** | 500k invocations/month | 1–5 alerts/day, well under cap |
| **Firebase Cloud Messaging (FCM)** | Unlimited free | Standard push-notification provider |
| **openFDA API** | Free, rate-limited 1000 req/min | Cloudflare Worker respects rate limit |
| **FDA RSS feed** | Free, unlimited | Backup polling channel |

**Total monthly cost at 100k users: $0.**

### Definition of done

- FDA publishes a recall at 9:00 am.
- At 9:14 am (next poll), Cloudflare Worker detects it.
- At 9:15 am, Supabase Edge Function writes an auto-drafted row; affected products flagged.
- At 9:15 am, Flutter users with the affected product in their stack get a push notification.
- By 9:17 am, a user opens the app and sees the red-banner Tier-1 alert with clear guidance.
- By Tuesday next day, Dr. Pham refines the copy; users see the refined version on their next app open.

### Effort

**30–50 hours** over 2–3 weeks. The architecture is simple; the work is writing the Cloudflare Worker + Edge Function + auto-draft template + Flutter subscription handler.

### What this changes about Phase 2+ / Phase 4

- **Phase 2** gains a "safety alerts queue" view for Dr. Pham's refinement work.
- **Phase 4** (reference-data hot-refresh) is the *catalog* fast-refresh path. Phase 1.5 is the *alerts* fast-refresh path. Both coexist; they're different problem shapes.

### Safety alerts are tier-agnostic — never Pro-gated

Important constraint for the future monetization layer (detailed in Phase 4.5): **Tier 1 CRITICAL safety alerts must fire for every user, free or Pro, no exceptions.** Push notifications for FDA Class I recalls, undeclared controlled substances, and acute hazards are a clinical-trust obligation, not a premium feature. Cheaper to send for free than to defend in court after a gated recall alert fails to reach a free user.

What *can* be Pro-gated: HIGH-tier advisories, deeper "why this was flagged" explanations, stack-level alert history, bulk-export of alert history.

---

## Phase 2 — Dr. Pham (and any reviewer) edits clinical copy without git

**Timeline:** 3–4 weeks part-time.
**Cost:** $0/month.
**Can run in parallel with Phase 3.**

### What it is

Today Dr. Pham edits `ingredient_interaction_rules.json` (and the other live data files) locally and sends them to you. The legacy `_Reviewed.json` snapshot pattern was retired on 2026-05-13 — the live file is now the single source of truth (see commit `7a1754a`). In Phase 2 we give her a **web-based editor** (extension of the Streamlit dashboard you already built) where she can:

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

## Phase 4.5 — Tiered Offline Architecture

**Timeline:** 4–6 weeks part-time.
**Cost:** $0/month.
**Depends on Phase 4 (hot-refresh) + Phase 1 (pipeline in CI).**
**Trigger:** cross 50k products in catalog, or Flutter bundle exceeds 60 MB.

### What it is

The architectural transition that keeps the Flutter app bundle size flat as the catalog grows from 10k → 250k. Based on Yuka's proven pattern (ship 1.6% locally, fetch the rest) adapted to our scale and offline requirements.

Three tiers of data, three delivery mechanisms:

```
┌─────────────────────────────────────────────────────────────┐
│  TIER 1 — App binary (<25 MB compressed)                    │
│  - Reference data (banned, harmful, interactions, etc.)     │
│  - Verdict shard: ~50k most-scanned products (~3 MB)        │
│  - Minimum offline UX: name, photo-thumbnail-pointer,       │
│    verdict, score, safe/not-safe                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 2 — Post-install downloadable shard                   │
│  (iOS ODR / Android Play Asset Delivery — both free)        │
│  - Top 150k products, verdict + basic safety flags          │
│  - ~15 MB zstd-compressed                                   │
│  - Triggers: first launch background download OR            │
│    explicit user opt-in ("Enable offline mode")             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 3 — Supabase on-demand (all 250k + detail blobs)      │
│  - Full ingredient list, detailed warnings, evidence        │
│  - Fetched on scan/search when online                       │
│  - 24h local cache (existing detailBlobProvider pattern)    │
└─────────────────────────────────────────────────────────────┘
```

### The offline UX contract — "minimum viable safety"

Per your existing requirement: when a user is fully offline and scans a product in Tier 1 or 2, they see:

- **Product identity:** name, brand, photo-thumbnail (cached if seen before, or a placeholder)
- **Verdict:** SAFE / CAUTION / POOR / UNSAFE / BLOCKED / NOT_SCORED
- **Score:** /100 equivalent + grade letter
- **Hard safety flags:** has_banned_substance, has_recalled_ingredient, has_harmful_additives (boolean, rendered as badges)
- **Interactions + stack function:** work entirely on-device because they use the local reference data + user's local stack

They do NOT see (requires network):
- Full ingredient breakdown
- Detailed warnings with clinical copy
- Evidence / PMID citations
- Formulation detail (proprietary blends, certification detail, proprietary_blend_audit)

This matches Yuka's offline contract and sets clear user expectations via an offline banner: *"Full details available when online."*

### Why it matters

- **Install size stays flat.** App bundle targets <80 MB forever, regardless of catalog size.
- **Offline scan still works** for the 90th-percentile product (top 150k is a huge practical majority).
- **Clinical-trust safety signal is offline-first.** Users never walk into a store, scan a product, and see "error, please connect to internet" for the top 150k products.
- **Network cost scales linearly with usage**, not with catalog size. User only pays bandwidth for products they actually scan.

### How to do it

**Step 4.5.1 — Identify the "most-scanned 50k" (Tier 1 shard).**

- Wait until Phase 5 observability gives you real scan analytics.
- Until then, proxy by: top brands + top 5 categories (gummies, capsules, softgels, powders, liquids) by product count.
- Rebuild the shard monthly — popularity shifts over time.

**Step 4.5.2 — Build the verdict-shard emitter in the pipeline.**

New pipeline stage: `build_verdict_shard.py` — reads the final DB and emits a compact SQLite file with just:

```sql
CREATE TABLE verdict_shard (
  dsld_id          TEXT PRIMARY KEY,
  barcode          TEXT,
  product_name     TEXT,
  brand_name       TEXT,
  photo_thumb_url  TEXT,       -- CDN URL, image cached client-side separately
  verdict          TEXT NOT NULL,
  score            REAL,
  grade            TEXT,
  has_banned       INTEGER,
  has_recalled     INTEGER,
  has_harmful      INTEGER,
  has_allergen     INTEGER,
  schema_version   TEXT NOT NULL,
  last_updated     TIMESTAMPTZ NOT NULL
);

CREATE INDEX verdict_shard_barcode_idx ON verdict_shard (barcode);
```

Emit three versions per build:
- `verdict_shard_tier1.sqlite` — top 50k (shipped in app binary)
- `verdict_shard_tier2.sqlite` — top 150k (ODR / Play Asset Delivery pack)
- `verdict_shard_tier3.sqlite` — full catalog (optional power-user download)

**Step 4.5.3 — Apply sqlite-zstd compression.**

Run each shard through `sqlite-zstd` row-level compression. Real-world results: 6.5x reduction. Our 150-byte/row schema should compress to ~25–30 bytes/row effective.

Target sizes post-compression:
- Tier 1 (50k): <5 MB
- Tier 2 (150k): <15 MB
- Tier 3 (250k): <25 MB

**Step 4.5.4 — iOS On-Demand Resources + Android Play Asset Delivery.**

- iOS: tag the Tier 2 shard as an ODR tag. Flutter plugin `flutter_on_demand_resources` or native Swift code triggers the download on first launch.
- Android: create a Play Asset Delivery on-demand pack. Flutter plugin `play_asset_delivery` triggers the download.

Both are free. Both download over WiFi by default.

**Step 4.5.5 — Snapshot + delta sync (not Supabase Realtime).**

For Tier 1 and Tier 2 shards, use HTTP-based snapshot + delta:

- Pipeline nightly builds both shards, uploads to R2 with version hash: `verdict_shard_tier1_v2026-04-19.sqlite.zstd`.
- `verdict_shard_manifest.json` on R2 tracks current version + SHA-256 + download URL per tier.
- Client checks manifest daily (if online). If version drift detected, downloads the new shard (background, WiFi-only).
- No Supabase Realtime websocket for product data. Only safety_alerts table uses Realtime (Phase 1.5) because those are time-critical small-volume events.

**Step 4.5.6 — Update Flutter data layer.**

Modify Flutter's CoreDatabase lookup logic:

```dart
// Pseudo-code
Future<Product?> findById(String dsldId) async {
  // 1. Try Tier 1 + Tier 2 local shards (single UNION query).
  final local = await _localVerdictDb.query(dsldId);
  if (local != null) return local;

  // 2. Online: query Supabase for the product row.
  if (await connectivity.isOnline) {
    final remote = await supabase.from('products').select().eq('dsld_id', dsldId).single();
    return remote;
  }

  // 3. Offline and not in local shards → return null with "offline miss" marker.
  return null;
}
```

Then update `detailBlobProvider` (already exists) to gracefully render the local verdict if the blob fetch fails offline.

**Step 4.5.7 — Offline-capability telemetry.**

Ship a telemetry event: every scan tagged as `{tier1_hit, tier2_hit, remote_online, remote_offline_miss}`. Phase 5 dashboards show:
- % of scans served by tier 1 (install-bundle)
- % by tier 2 (post-install pack)
- % by remote
- % that hit offline miss (product wasn't in any tier, no network)

Goal: keep offline-miss rate under 5% of total scans. If it creeps up, the Tier 1/2 selection is wrong — adjust the "most-scanned" algorithm.

### Free options

| Component | Free option | Notes |
|---|---|---|
| Storage for shards | Cloudflare R2 (10 GB free, zero egress) | Already used in Phase 1 |
| Post-install delivery | iOS ODR + Android Play Asset Delivery | Free, native platform features |
| Compression | sqlite-zstd (MIT license) | Free open-source SQLite extension |
| Sync layer | Snapshot + delta via HTTP Range | Free; no PowerSync subscription needed |

### Definition of done

- Flutter app binary stays under 60 MB at 250k catalog scale.
- Tier 2 pack downloads on first launch (WiFi-only), ~15 MB, takes <30s on typical broadband.
- Offline scan of any product in top 150k returns verdict + safe/not-safe + basic identity in <50ms.
- Offline scan of a product beyond 150k returns a clean "product not available offline" message with the option to save for later.
- Online scan of any 250k product returns full detail blob in <300ms.
- Telemetry confirms offline-miss rate <5%.

### Effort

**60–80 hours** over 4–6 weeks. Bulk of the work is in Flutter (ODR / Play Asset Delivery integration), not the pipeline. Pipeline-side: ~2 days to add `build_verdict_shard.py` + sqlite-zstd integration + manifest publication.

### Monetization layer — Pro-tier offline gating

**Free tier (default):**
- Tier 1 shard (top 50k in app binary) — always available, including offline
- Tier 3 (Supabase on-demand) — works when online
- Full safety alerts (Phase 1.5, CRITICAL tier) — **always on, never gated**
- Basic interactions + stack function — on-device, always on

**Pro tier (paid):**
- Everything above, PLUS:
- Tier 2 post-install pack download (top 150k offline) — the big expansion
- Unlimited offline detail blob caching (free tier capped at ~50 cached products)
- Full push-notification tier (free tier gets only CRITICAL, Pro gets HIGH too)
- Optional: family-plan stack sharing, export features, advanced dashboards

This mirrors Yuka's approach exactly: their free tier is online-only; their Premium unlocks the 100k offline pack. Proven model in the same vertical.

#### The critical ethical constraint — safety alerts are never Pro-gated

Tier 1 CRITICAL safety alerts (FDA Class I recalls, undeclared controlled substances, acute health hazards) **must never be Pro-gated.** Reasoning:

- A free user who bought a now-recalled supplement needs that push notification regardless of subscription tier.
- Charging for the "will this kill me" signal is a clinical-trust failure and creates liability exposure.
- Practically: the marginal cost of a push notification is $0; there's no business reason to gate it.

What *can* be Pro-gated: HIGH tier (class II/III recalls, warning letters), CATALOG tier (copy refinements), and richer explanations of why a product is flagged.

What *cannot* be gated: the actual recall notification for products in a user's stack.

This aligns with the FDA's own consumer protection guidance and keeps the app defensible against "they gated a safety feature" user stories.

#### Infrastructure implications

Build the tier gate into the architecture from day one so we don't retrofit later:

1. **User tier field** in Supabase `auth.users` metadata: `tier: 'free' | 'pro'`.
2. **Client checks tier** before offering Tier 2 download. Free users see a "Upgrade to Pro for offline mode on 150k products" CTA.
3. **Manifest endpoint** validates tier for Tier 2 pack URL signing — even if a free user bypasses the client check, the signed URL rejects them.
4. **Safety alerts subscription** is tier-agnostic — all users subscribe to the `safety_alerts` Realtime channel, and Tier 1 CRITICAL fires for everyone.
5. **Telemetry dimension** added — scan coverage segmented by tier to track Pro-value delivery.

Implementation cost: small (~1 week of extra Flutter work on top of Phase 4.5), done as part of Phase 4.5 rather than deferred.

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
| **1.5** | **Safety Alert Short Path — <15 min FDA-recall → user** | **2–3 weeks** | **$0** | **Phase 1 (ship before public beta)** |
| **2** | Dr. Pham edits clinical copy via web UI → PR | 3–4 weeks | $0 | Phase 1 (recommended) |
| **3** | Monthly scheduled DSLD intake by category with delta detection | 2 months | $0 | Phase 1 |
| **4** | Reference-data changes auto-propagate to affected products + Flutter | 2–3 months | $0 | Phase 1 |
| **4.5** | **Tiered offline architecture (Yuka-style) — app stays <60 MB at 250k products** | **4–6 weeks** | **$0** | **Phase 4, triggered when catalog > 50k** |
| **5** | Full observability, alerting, audit trail, staging | ongoing | $0–$25/mo | Phases 1–4 |

**6 months from today:** a teammate adds a new brand by making a one-line PR; intake runs monthly without you; Dr. Pham's typo fix reaches users within an hour of her saving; FDA recalls hit affected users' phones in under 15 minutes; the app scales from 10k → 250k products without changing the architecture; you can take a week off and nothing breaks.

### Scaling to 250k — the tiered offline architecture

**What stays the same:**
- The 3-stage pipeline (clean → enrich → score) — same code, just runs on more data.
- The validator + test suite — unchanged.
- The dashboard — adds pagination and deeper filtering, but architecture holds.
- Dr. Pham's review flow — she authors *reference data* (banned, harmful additives, interactions), not per-product copy. Her work scales independently of product count.

**What must be right before 250k — and this is its own phase (Phase 4.5).** See [Phase 4.5](#phase-45--tiered-offline-architecture) below.

### How comparable apps solve this

The problem "scanning app with millions of products + offline capability" has been solved in the market. Quick competitive scan:

| App | Products | App binary | Offline strategy |
|---|---|---|---|
| **Yuka** | ~6M food+cosmetics | 75–126 MB | Top **100k** scanned locally (post-install download, Premium-only); free tier online-only |
| **Open Food Facts** (smooth-app) | ~3M | — | Top 1k + recently-viewed cached; full 7GB dump never bundled |
| **MyFitnessPal** | ~14M foods | — | Recently-logged cache only; new search needs network |
| **Cronometer** | ~15k curated | — | Effectively online-only; long-standing user complaint thread since 2022 |
| **EWG Healthy Living** | 200k | — | Online-first (not documented offline) |

**Two lessons from this:**

1. **Nobody ships the whole database.** Yuka ships only **1.6%** of their catalog on-device, and they're at 6M products. At 250k we could ship more, but there's no need.
2. **"No offline scan" is the clinical-trust failure mode.** Cronometer's forum thread is the canonical warning — health-scanner users *really* notice when the app fails at the grocery store. Even a degraded-but-present offline mode (verdict + score only) beats an error message.

### Platform constraints (2025–2026)

- **iOS cellular-download soft ceiling:** apps >200 MB prompt the user before downloading on cellular. Apps >150 MB see meaningful conversion loss.
- **iOS On-Demand Resources:** individual tags ≤ 512 MB (ideal <64 MB); asset packs up to 8 GB on iOS 18+; total budget per app up to 20 GB.
- **Android Play Asset Delivery:** install-time packs ≤ 1 GB; on-demand/fast-follow up to 30 GB total.
- **Practical install-size sweet spot for a consumer health app: under 80 MB.** Beyond that, conversion drops.

### SQLite compression math

- Naive: **250k rows × ~2.5 KB ≈ 625 MB.** Non-shippable.
- But ~2.5 KB includes ingredients + detailed warnings + evidence — content we explicitly want *online*.
- **Verdict-only shard** (dsld_id + barcode + verdict + score + score_version + timestamp): ~40 bytes/row.
  - 50k × 40 bytes = **2 MB raw, ~1 MB zstd**.
  - 150k × 40 bytes = **6 MB raw, ~3 MB zstd**.
  - 250k × 40 bytes = **10 MB raw, ~5 MB zstd**.
- **Verdict + basic safety flags + brand/product name** (~150 bytes/row, what's needed for offline "photo/score/name/safe/not-safe" UI):
  - 50k × 150 bytes ≈ **7.5 MB raw, ~2–3 MB zstd**.
  - 250k × 150 bytes ≈ **37.5 MB raw, ~10–15 MB zstd** using sqlite-zstd row-level compression (real-world benchmarks show 6.5x reduction).

**Conclusion:** even at full 250k, a meaningfully-useful offline shard fits in <20 MB compressed. The 575 MB number from my earlier note was wrong because it assumed full detail locally. The right architecture ships minimal rows locally and fetches detail on-demand — exactly what you described.

### What must be right before 250k

- **Product detail blobs always fetch from Supabase on-demand.** Flutter ships only reference data (~10 MB) and a verdict shard (~15 MB compressed). Total ~25 MB for the "offline scorecard."
- **Tiered local shard strategy** (see Phase 4.5 for details).
- **Aggressive reference-data reverse indexes.** When Dr. Pham changes a harmful_additive at 250k scale, the "affected products" lookup must be indexed (Phase 4). A naive scan at 250k would be minutes, not seconds.
- **Snapshot+delta sync** (not Supabase Realtime) for the verdict shard. Nightly compressed SQLite snapshot on R2 + daily delta patches; client fetches via HTTP Range requests.
- **CDN-cached product blobs.** Cloudflare CDN on Supabase Storage drops latency from ~200ms to ~30ms for the on-demand detail fetch.

### What doesn't need to be built until later

- Full-text search engine (ElasticSearch etc.) — SQLite FTS5 handles up to 10M rows fine with ~30% overhead. Deferred indefinitely.
- Multi-region deploy — defer until user count warrants it.
- ML-driven recommendations — defer indefinitely unless product direction requires it.
- **PowerSync** (a commercial Postgres↔SQLite sync engine many apps use) — adds cost and complexity we don't need. Our snapshot+delta pattern is simpler and fits our weekly pipeline cadence.

---

## My honest recommendation

**Do Phase 1 + Phase 1.5 before public beta launch. Everything else can wait.**

Reasoning:
- **Phase 1** removes the "only Sean can build" bottleneck.
- **Phase 1.5** is the safety-critical fast lane. A public app without same-day recall alerts is a clinical-trust liability. If a user's supplement got recalled yesterday and our monthly build hasn't run yet, that's not an inconvenience — that's a user-safety failure.
- **Phase 2** (Dr. Pham web editor) is a productivity upgrade, not a safety blocker. Nice-to-have for beta; must-have for V1.
- **Phase 3–5** follow as the business grows.

**Minimum-viable-safe shippable beta = Phase 1 + Phase 1.5.** Total time: 4–6 weeks of focused work.

When you're ready, I can:
- Draft `.github/workflows/build-db.yml` based on your actual `run_pipeline.py` signature.
- Write the `scripts/storage_client.py` abstraction so the pipeline can read from R2 or Supabase Storage interchangeably.
- Migrate one brand's raw JSON to the bucket as a proof-of-concept.
- Draft the Cloudflare Worker `safety-alert-poller.ts` + Supabase Edge Function `draft-safety-alert/index.ts` + the `safety_alerts` table migration.
- Write the Flutter Realtime subscription + FCM trigger.

Just say when.
