# PharmaGuide — Pipeline Operations Handbook

**Audience:** Anyone running, reviewing, or approving a pipeline change.
**Purpose:** Operational playbook for the multi-person era. Answers *how do I actually do this?*
**Companion docs:**
- [`AUTOMATION_ROADMAP.md`](AUTOMATION_ROADMAP.md) — the phased vision.
- [`PIPELINE_MAINTENANCE_SCHEDULE.md`](PIPELINE_MAINTENANCE_SCHEDULE.md) — who does what, how often.
- [`scripts/PIPELINE_OPERATIONS_README.md`](../scripts/PIPELINE_OPERATIONS_README.md) — technical command reference.

This document is the **people-side** operations handbook. The technical reference in `scripts/` covers every exact command. This file answers: who needs to care about which command, what are the guardrails, and what happens when things go sideways.

---

## The shape of a pipeline change

Every change — a Dr. Pham copy edit, a new brand, a new FDA recall, a harmful-additive wording tweak — flows through the same 5-stage funnel:

```
  INGEST    →    AUTHOR    →    VALIDATE    →    BUILD    →    DEPLOY
  (raw)          (human)         (automated)      (CI)          (Supabase→Flutter)
```

Each stage has different owners, different tooling, different failure modes. Understanding the funnel is the key to multi-person operations.

### Stage 1 — INGEST (data arrives)

**What happens:** raw data enters the system — from NIH DSLD (products), FDA (recalls), PubMed (science), or manually curated.

**Who owns it:** Pipeline operator (today). Automated workflows + data curator (Phase 3+).

**Tools:**
- `scripts/dsld_api_sync.py` — NIH DSLD product fetching
- `scripts/api_audit/fda_weekly_sync.py` — FDA regulatory data
- `scripts/api_audit/*.py` — per-source enrichment (UMLS, PubMed, ChEMBL, etc.)
- Cloud storage bucket — landing zone for raw JSON

**Failure modes:**
- NIH API returns errors → retry with backoff (already in `dsld_api_client.py`)
- FDA format changes → workflow fails loudly, human investigates
- Duplicate product IDs → deduped by canonical ID before commit

**Guardrail:** raw data is never committed to the repo directly. It flows through the bucket → a PR gets opened. Humans approve the PR before raw data enters the processing pipeline.

### Stage 2 — AUTHOR (human writes clinical voice)

**What happens:** clinical authors (Dr. Pham, future reviewers) write user-facing strings. This is where the system transforms raw facts into calm, accurate, nocebo-safe copy.

**Who owns it:** Dr. Pham (primary). CSO or second clinical reviewer (approvals).

**Tools:**
- Dashboard: `streamlit run scripts/dashboard/app.py` → Quality → Clinical Copy
- (Phase 2) Web-based editor with PR opener
- (Phase 2) Strict validator runs on every PR automatically

**Failure modes:**
- Author writes SCREAM copy ("AVOID!") → validator fails → PR blocked
- Author writes encyclopedic opener ("Aspartame is a...") → validator fails
- Author includes numeric stats in body ("30% of users") → validator fails
- Author writes body >200 chars → validator fails

**Guardrail:** validator is the enforcement layer. Author can't merge bad copy even accidentally.

### Stage 3 — VALIDATE (automated checks)

**What happens:** every PR that touches pipeline data or code gets machine-tested before merge.

**Who owns it:** automated (CI). Humans only touch this when adding new validators.

**Tools:**
- `.github/workflows/validate-pr.yml` (Phase 2)
- `scripts/validate_safety_copy.py --strict`
- `pytest scripts/tests/` (3,957 tests)
- `scripts/db_integrity_sanity_check.py`
- `scripts/coverage_gate.py`
- `scripts/enrichment_contract_validator.py`

**Failure modes:**
- Validator or test fails → PR cannot merge → author fixes + re-pushes
- New failure mode discovered → add a new test, add a new validator rule

**Guardrail:** no PR merges with a red check. Branch protection in GitHub enforces this.

### Stage 4 — BUILD (pipeline assembles final DB)

**What happens:** once merged to main, CI runs the full pipeline on the new state: clean → enrich → score → build_final_db. Output is a SQLite file + detail blobs + manifest.

**Who owns it:** automated (CI) via `.github/workflows/build-db.yml` (Phase 1).

**Tools:**
- `scripts/run_pipeline.py`
- `scripts/build_final_db.py`
- Cloud storage bucket (for raw data input + build artifact caching)

**Failure modes:**
- Enrichment exception on one product → product goes to `errors/` folder, build continues with 99% coverage, ops reviews
- Out-of-memory on CI → split build into batches, add retry
- Schema drift → `db_integrity_sanity_check.py` fails the build

**Guardrail:** coverage gate requires >95% of products to score successfully. A build with <95% coverage doesn't deploy.

### Stage 5 — DEPLOY (Supabase → Flutter)

**What happens:** final DB is synced to Supabase. Flutter app reads reference data from its local asset bundle, and fetches product detail blobs from Supabase on-demand (at V1+ scale).

**Who owns it:** automated (CI). Pipeline operator for emergency rollbacks.

**Tools:**
- `scripts/sync_to_supabase.py` — catalog + reference data
- Supabase dashboard for manual inspection
- Flutter asset sync (manual today; automated in Phase 4)

**Failure modes:**
- Supabase rate-limit → retry with backoff
- Sync interrupted mid-way → partial state; tooling has `--cleanup` flag to fix
- Flutter asset out of sync → users on offline mode see stale reference data
- Product blob fetch fails on client → graceful fallback to "details unavailable; try again in a moment"

**Guardrail:** previous Supabase snapshot retained for 30 days. One-click rollback (Phase 5).

### Stage 5b — INSTANT ALERT DEPLOY (FDA recalls / bans, Phase 1.5)

**What happens:** parallel to Stage 5, a dedicated fast lane pushes safety alerts to users within 15 minutes of FDA publication — without a full pipeline rebuild.

**Who owns it:** automated (Cloudflare Worker + Supabase Edge Function). Safety-alert watcher (pipeline operator) monitors via Slack.

**Tools:**
- Cloudflare Worker `safety-alert-poller.ts` — polls openFDA + FDA RSS every 15 min
- Supabase Edge Function `draft-safety-alert` — classifies tier, auto-drafts conservative copy, inserts `safety_alerts` row
- Supabase Realtime — pushes new rows to subscribed Flutter clients
- Firebase Cloud Messaging — Tier 1 push notifications
- Dashboard safety-alerts queue — Dr. Pham refines copy within 24–48 hrs

**Failure modes:**
- Poller misses a recall (API returned error) → next poll 15 min later picks it up; second-order fallback is the weekly FDA sync
- Auto-draft classifies tier wrong → safety-alert watcher manually overrides within minutes
- FCM push fails for subset of devices → in-app banner still fires on next open
- False-positive alert (bad match) → safety-alert watcher marks `status='superseded'` → Realtime retracts

**Guardrail:**
- Every auto-drafted alert goes to Slack `#safety-alerts` for human eyeballing.
- Supabase Edge Function rate-limits itself to 10 alerts/hour to prevent runaway firing on a bad FDA data day.
- Tier 1 push notifications cap at 3/day per user (hard-coded client-side) to prevent push fatigue.

---

## The roles and their permissions

### Pipeline operator (today: Sean)

**Can do:**
- Merge PRs
- Trigger manual builds
- Access Supabase service key
- Modify GitHub Actions workflows
- Access cloud storage bucket
- Configure GitHub repo settings

**Should not do (without a second approver):**
- Deploy directly to Supabase production without a PR
- Force-push to main
- Disable CI checks
- Rotate shared secrets unilaterally

### Clinical author (today: Dr. Pham)

**Can do:**
- Edit authored copy fields in the web UI (Phase 2)
- Open PRs via the UI
- View the Clinical Copy dashboard
- Comment on PRs
- **Refine auto-drafted safety-alert copy** in the dashboard's safety-alerts queue (Phase 1.5). Edits push live to Supabase Realtime within seconds.

**Cannot do:**
- Edit severity / evidence_level / mechanism / PMIDs (locked at form layer)
- Merge PRs (approval required from pipeline operator / CSO)
- Access Supabase service key
- Override tier classification on safety alerts — that's the safety-alert watcher's call (it affects push-notification behavior)

### Safety-alert watcher (Phase 1.5 — today: Sean; future: on-call rotation)

**Can do:**
- Monitor `#safety-alerts` Slack channel
- Mark auto-drafted alerts as `superseded` (false-positive retraction)
- Reclassify tier on an alert (CRITICAL ↔ HIGH ↔ CATALOG)
- Trigger fallback `fda_weekly_sync.py` if the poller degrades
- Escalate P0 incidents to the pipeline operator / CSO

**Cannot do:**
- Author clinical copy (that's Dr. Pham's job; watcher only classifies/retracts)
- Change poller schedule without a PR (config change, auditable)

### Safety reviewer / CSO (future)

**Can do:**
- Approve clinical-copy PRs (second approver)
- Request changes on PRs
- Review incident post-mortems
- Quarterly: read through audit trail

**Cannot do:**
- Merge without validator passing
- Edit pipeline infrastructure

### Data curator / ops (future, part-time role)

**Can do:**
- Review monthly intake PRs
- Flag bad products for exclusion
- Update brand allowlist (`config/brands.json`)
- Update category config (`config/categories.json`)

**Cannot do:**
- Merge clinical-copy changes (not clinical judgment)
- Modify pipeline code

### Engineer / devops (future)

**Can do:**
- Modify workflows, validators, pipeline code
- Debug CI failures
- Rotate secrets
- Performance optimization

**Cannot do:**
- Approve clinical-copy PRs (not clinical judgment)

---

## Operational playbooks

These are the "oh no, what do I do now" runbooks. Short and specific.

### Playbook 1 — Monthly intake PR arrived, how do I review?

1. Open the PR. The title looks like *"Monthly intake 2026-05: +42 gummies, +18 capsules"*.
2. Check the summary comment — confirms which DSLD IDs are new.
3. Click through 3–5 randomly sampled new product JSON files. Do they look like real products? (Brand name, ingredients, UPC all populated?)
4. Check the CI status — validator + tests green?
5. If yes to all: click Approve → Merge.
6. If something looks off (garbled brand, empty ingredient list, duplicate UPCs):
   - Comment on the PR with the specific product IDs.
   - Add them to `config/intake_denylist.json`.
   - Push a follow-up commit that removes those files from the PR.
   - Re-review.

**Total time:** 5–15 minutes.

### Playbook 2 — Dr. Pham submitted a clinical-copy PR, how do I review?

1. Open PR. CI should already be green.
2. Read the authored strings in the diff view. Do they:
   - Match the entry's `mechanism` / `reason`?
   - Use conditional framing ("If you have X, talk to...")?
   - Avoid SCREAM / derivation openers / catastrophizing?
3. Spot-check 1 entry in the dashboard's random-entry picker.
4. If all good: Approve + Merge.
5. If a specific string feels off:
   - Click "Request changes" with a comment on the offending entry.
   - Suggest the fix in the PR comments — let Dr. Pham accept or propose alternative.

**Total time:** 15–30 minutes.

### Playbook 3 — Build failed, what now?

1. Check GitHub Actions → identify the failing step.
2. Three common categories:
   - **Validator failed** → someone merged bad copy. Revert the merge PR, open a fix PR.
   - **Tests failed** → code regression. Check the pytest output, revert if needed.
   - **Infra failed** (timeout, OOM, API rate-limit) → re-run the workflow. If it fails twice, investigate.
3. If the failure blocked a deploy, the previous Supabase state is still live — users aren't affected.
4. Post to Slack: *"Build failed, investigating, no user impact."*
5. Fix → merge → re-build.

**Total time:** 5–60 minutes depending on category.

### Playbook 4 — A product has wrong data in the app, what now?

1. Identify the product — get the DSLD ID.
2. Check the dashboard → Product Inspector → search by DSLD ID.
3. Read the product blob — what's wrong? Score? Warning? Missing ingredient?
4. Categorize:
   - **Data was wrong in source** (NIH DSLD has bad data) → add to `config/product_overrides.json` with corrected values; rebuild.
   - **Data was wrong in reference** (our harmful_additives had wrong severity, etc.) → open a clinical-review PR.
   - **Pipeline bug** (enrichment misfired) → file a bug issue with repro steps; add a regression test.
5. Depending on severity:
   - User-facing wrong number → ship fix same day.
   - Cosmetic issue → next weekly build.

**Total time:** 30 minutes – 4 hours depending on category.

### Playbook 5 — I need to roll back a bad release

1. **Assess:** what's wrong, how many users affected? If <100 users in last hour, consider fixing forward rather than rolling back.
2. **Decide rollback target:** the previous Supabase snapshot (last night's) or further back?
3. **Execute:**
   - Paid Supabase: point-in-time restore via dashboard (~2 min).
   - Free tier: restore from R2 snapshot → `python3 scripts/restore_from_snapshot.py --target {snapshot_id}` (~5 min).
4. **Verify:** spot-check 3–5 products via the dashboard's Product Inspector. Do they match the old values?
5. **Communicate:** post to Slack / status page.
6. **Post-mortem:** within 48 hrs, write up what happened.

**Total time:** 15–30 minutes.

### Playbook 6 — A teammate wants to add a brand

1. Teammate uploads the brand's raw DSLD JSON to `r2://pharmaguide-pipeline/raw/{Brand}/*.json` (their browser / s3 tool).
2. Teammate opens a PR adding `{"name": "{Brand}", "enabled": true}` to `config/brands.json`.
3. Pipeline operator reviews:
   - Spot-check 3 uploaded files.
   - Confirm brand name not already present.
4. Approve + merge → weekly build picks it up automatically.

**Total time:** 5 minutes per side.

### Playbook 7 — Critical FDA recall just fired (Phase 1.5)

**If you're woken up by a Tier 1 alert in `#safety-alerts`:**

1. **Read the Slack post** (auto-generated by the Edge Function). It shows: source (openFDA / FDA RSS), recall ID, tier classification, auto-drafted copy, matched canonical IDs.
2. **Sanity-check the match.** Does the FDA's product/brand/ingredient name legitimately map to something in our catalog? Common false-positive causes:
   - FDA recall is about a food item, not a supplement (non-supplement FDA recalls sometimes slip through).
   - Brand name overlap (two brands share a word).
   - Canonical-ID match too loose.
3. **If the match is correct:**
   - Let the alert stand. Push notifications have already fired. No manual action needed.
   - Ping Dr. Pham in Slack to refine the auto-drafted copy within 24 hrs.
4. **If the match is a false positive:**
   - In the dashboard → `#safety-alerts-queue` → click "Mark superseded" on the offending row.
   - Supabase Realtime pushes the retraction to clients; banners disappear on next app open.
   - Post to Slack: *"False-positive Tier 1 alert retracted at HH:MM, root cause: {reason}. No user-impact push fired — matched users now see the retraction on next open."*
5. **If tier was wrong (should have been Tier 2/3, not Tier 1):**
   - Reclassify via the dashboard → updates the row → clients handle the new tier on next Realtime update.
6. **Post-mortem:** any Tier 1 false positive or wrong-tier gets a 3-paragraph write-up within 48 hours — push notifications are expensive user trust; misfires should be rare and documented.

**Total time:** 5–30 minutes depending on how clean the match was.

### Playbook 8 — The safety-alert poller is down

**Signals:**
- No new `safety_alerts` rows in 2+ hours (verify via dashboard or Supabase).
- UptimeRobot flag on the Cloudflare Worker endpoint.
- FDA publishes a known recall, nobody gets notified.

**Response:**

1. Check Cloudflare Workers dashboard → `safety-alert-poller` → look at recent executions.
2. If executions stopped: check for a deploy error, revert last worker version.
3. If executions are firing but writing nothing: check Supabase Edge Function logs for `draft-safety-alert` errors.
4. If FDA API is down on their end: out of our hands, but log it.
5. **Meanwhile, trip the fallback:** kick off `scripts/api_audit/fda_weekly_sync.py` manually to catch anything the poller missed. This won't get sub-hour latency but prevents the catalog from drifting.
6. Post to Slack: *"Safety poller degraded at HH:MM, fallback manual sync running. ETA to restore: {estimate}."*

**Total time:** 15–45 minutes to restore; fallback buys you hours of safety margin.

### Playbook 9 — The monthly cron didn't fire

1. Check GitHub Actions → `monthly-intake.yml` workflow.
2. If it's listed but ran as "failed": click through, identify the error, fix.
3. If it's listed and ran as "success" but opened no PR: check state file, maybe no new products this month. Usually benign.
4. If it's NOT listed at all: the cron may be disabled. Go to Actions → workflow → enable.
5. Run manually: Actions → workflow → "Run workflow" button. Pick main branch.

**Total time:** 5–15 minutes.

---

## Standard operating procedures

### SOP-1 — Opening a PR (for any teammate)

- Branch name: `{your-handle}/{short-description}` (e.g., `dr-pham/fix-aspartame-copy`)
- Commit message: imperative mood, short summary (e.g., `"fix: clarify aspartame PKU framing"`)
- PR title: same as commit summary
- PR description: what changed, why, how tested
- Assign yourself
- Request review from appropriate role (clinical-copy → CSO; pipeline code → pipeline operator)
- Never merge your own PR (even if you have the permission)

### SOP-2 — Running the pipeline locally (while Phase 1 is in progress)

```bash
# 1. Activate env
cd /Users/seancheick/Downloads/dsld_clean

# 2. Run the pipeline for one brand
python3 scripts/run_pipeline.py scripts/products/output_Nature_Made

# 3. Build the final DB from all enriched+scored dirs
python3 scripts/build_final_db.py \
  --enriched-dir scripts/products/output_{Brand}_enriched/enriched ... \
  --scored-dir scripts/products/output_{Brand}_scored/scored ... \
  --output-dir /tmp/local_build

# 4. Run the release-gate validator
python3 scripts/validate_safety_copy.py --strict

# 5. Run the test suite
python3 -m pytest scripts/tests/ -q

# 6. Dry-run Supabase sync
python3 scripts/sync_to_supabase.py /tmp/local_build --dry-run

# 7. If dry-run looks good, commit to a branch, open a PR, let CI run real sync
```

Full details in [`scripts/PIPELINE_OPERATIONS_README.md`](../scripts/PIPELINE_OPERATIONS_README.md).

### SOP-3 — Approving a Supabase sync

Never do a manual prod sync from your laptop unless it's an emergency.

Prod syncs should flow through CI:
1. Merge PR to main.
2. Build workflow runs → validator → build → sync.
3. If sync fails, CI logs show the error.
4. If sync succeeds, you'll see a Slack notification.

If you must sync manually (e.g., CI broken):
1. Pull latest main.
2. Run full test suite locally (`pytest scripts/tests/ -q`).
3. Run `validate_safety_copy.py --strict`.
4. Run `python3 scripts/sync_to_supabase.py <build_dir> --dry-run`.
5. Only if all three are green: drop `--dry-run` and sync for real.
6. Post to Slack: *"Manual sync completed, reason: {CI was down}. Verified by {name}."*

### SOP-4 — Rotating a secret

1. Generate new secret (API key, Supabase service key, etc.) via the upstream provider's dashboard.
2. Update GitHub Secrets → `{SECRET_NAME}` → paste new value.
3. Trigger a test workflow run — confirm it works.
4. Revoke old secret at upstream provider.
5. Post to Slack: *"Rotated {SECRET}, completed {YYYY-MM-DD}."*

Rotate quarterly at minimum, or immediately if a secret is suspected compromised.

---

## Monitoring & alerting

What you should have watching the system (most are free).

### Must-have (Phase 1 + free)

- **GitHub Actions build history** — every failure shows up in the Actions tab
- **Slack webhook for builds** — notifications on success/failure
- **Supabase logs** — accessible via Supabase dashboard
- **Clinical Copy dashboard** — manual Friday check

### Should-have (Phase 3+, still free)

- **UptimeRobot** — pings Supabase + Flutter endpoints every 5 min, alerts on downtime
- **Grafana Cloud free tier** — 10k metric series; connect Supabase logs for richer dashboards
- **Sentry free tier** — 5,000 events/mo; catches exceptions in CI + dashboard

### Nice-to-have (Phase 5, still mostly free)

- **PagerDuty** or similar — only when you have >2 people on-call
- **Datadog** or similar — only at significant user scale

---

## Security & access control

### API keys and secrets

- All secrets live in GitHub Secrets (for CI) or 1Password (for human access).
- Never commit secrets to the repo. `.env` is gitignored.
- Rotate quarterly.
- Revoke immediately if a laptop is lost.

### Repo access tiers

| Role | GitHub permission |
|---|---|
| Pipeline operator | Admin |
| Engineer | Write |
| Clinical author | Write (limited to branches via branch protection) |
| Safety reviewer / CSO | Write |
| Data curator | Triage (approve intake PRs, no code merge) |
| Investors / advisors | Read |

### Supabase access tiers

| Role | Supabase access |
|---|---|
| Pipeline operator | Service role key (via GitHub Secrets only, not personal access) |
| Engineer | Project admin |
| Clinical author | No direct access (edits via UI only) |
| Read-only analyst | Anon key (read-only) |

### Data sensitivity

- **Public data:** product catalog, reference databases, authored copy → all OK to be in the repo.
- **Internal data:** intake state files, build manifests → keep in the repo (gitignored for ephemeral artifacts).
- **Secret data:** API keys → secrets manager only, never in code.
- **PII:** we don't collect it. Keep it that way. Flutter user profiles are client-side only.

---

## Cost watch

Today: ~$0/month (everything on free tiers).

Projected monthly cost at common milestones:

| Milestone | Expected cost |
|---|---|
| 15 brands, 5k products, 100 active users | $0–$5 (Supabase pro if DB >500 MB) |
| 50 brands, 20k products, 5k active users | $25–$50 (Supabase Pro + extra storage) |
| 100 brands, 50k products, 50k active users | $100–$300 (multiple Supabase projects, CDN, monitoring) |
| 500 brands, 200k products, 500k active users | $2k–$5k (upgrades across the stack) |

At those milestones, cost review makes sense. Before then, stay on free tiers.

---

## Documentation discipline

Four doc families to keep alive:

| Doc | Update cadence | Who |
|---|---|---|
| `docs/AUTOMATION_ROADMAP.md` | Quarterly | Pipeline operator |
| `docs/PIPELINE_MAINTENANCE_SCHEDULE.md` | When cadence changes | Pipeline operator |
| `docs/PIPELINE_OPERATIONS_README.md` (this doc) | When playbooks change | Pipeline operator |
| `docs/incidents/*.md` | Per incident | Whoever ran the incident |
| `scripts/*.md` (technical refs) | When commands/schema change | Engineer |

**Rule:** if you find yourself answering the same question twice in Slack, that answer belongs in a doc.

---

## What's explicitly out of scope for this document

- **Exact commands** — see [`scripts/PIPELINE_OPERATIONS_README.md`](../scripts/PIPELINE_OPERATIONS_README.md).
- **Database schema** — see [`scripts/DATABASE_SCHEMA.md`](../scripts/DATABASE_SCHEMA.md).
- **Scoring algorithm** — see [`scripts/SCORING_README.md`](../scripts/SCORING_README.md).
- **Architecture decisions** — see `docs/TECH_STACK_2026.md` and related ADRs.

This doc is about *who, when, and how* — the human layer on top of the technical stack.

---

## Version

- v1.0 — 2026-04-18 — initial (multi-person era; paired with `AUTOMATION_ROADMAP.md` Phase 0).

Revise quarterly or whenever the operating model changes.
