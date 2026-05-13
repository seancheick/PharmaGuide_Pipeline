# ADR-0001 — Release pipeline safety for catalog & detail-blob storage

**Status:** ACCEPTED (2026-05-12)
**Date:** 2026-05-12
**Authors:** Sean Cheick (decisions), Claude (drafting)
**Affects:**
  - `scripts/release_full.sh`
  - `scripts/cleanup_orphan_blobs.py` (or its current home)
  - `batch_run_all_datasets.sh` (consumer)
  - Supabase storage bucket `pharmaguide` (detail-blob layout)
  - Pipeline manifest schema (new table `catalog_releases`)
  - PharmaGuide Flutter repo (`assets/db/`, new `make verify-bundle` target, CI gate)
**Related:**
  - `docs/PIPELINE_OPERATIONS_README.md`
  - `docs/PIPELINE_MAINTENANCE_SCHEDULE.md`
  - `scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md` (precedent for heavyweight ADR style in this repo)

---

## Catalyst

On 2026-05-12, a Garden of Life CBD product (DSLD 222862) opened on the user's iPhone with no `banned_substance_detail` rendering. Investigation revealed the bundled Flutter catalog on `main` was `v2026.05.11.164208`, while the Supabase orphan-cleanup at 14:49 the same day had purged every blob not referenced by the just-built `dist/` index (`v2026.05.12.203133`). The bundled catalog's blob hashes were deleted from storage; blob fetches returned 404; UI fell back to generic copy.

The new bundle (`v2026.05.12.203133`) had been written to the Flutter repo working tree by the pipeline's import step at ~17:02 and committed at 17:16 — but onto the wrong branch (`chore/pr-6a-decompose-interaction-warnings`), never merged into `main`. The pipeline reported success and the cleanup proceeded under the silent assumption that the bundled catalog matched dist.

Immediate workaround: cherry-pick `41e3e30` onto `main` (commit `c706b4b`). This realigned the bundled catalog with current Supabase storage and restored detail-blob fetches.

This ADR addresses the architectural gap that allowed silent corruption of state.

---

## Problem statement — invariants the system fails to enforce

| # | Invariant | Today's behavior |
|---|---|---|
| **I1** | No blob deletion may break a catalog version that any installed app could be running. | Cleanup deletes everything not in current `dist/`'s index. |
| **I2** | The set of "live" catalog versions is explicit, not inferred from recency. | No registry; "current" is the most recently built `dist/`. |
| **I3** | Destructive operations are reversible within a recovery window. | Hard-delete via Supabase storage API. |
| **I4** | Pipeline state inconsistency must fail loudly, not silently drift. | Cleanup ran while bundled-on-main was stale; no warning. |
| **I5** | The Flutter bundle commit is a pipeline output, not a manual followup. | Script prints "next steps" and exits with success. |

The 2026-05-12 incident is the intersection of I1+I4+I5 firing simultaneously. Enforcing any one of them properly would have made the failure loud rather than silent.

### Additional correctness invariants (architectural review)

I1–I5 are derived from the 2026-05-12 incident. The following five invariants did not cause the incident but must be enforced for the design to be production-safe — they protect against failure modes that have not yet occurred but are inevitable at scale.

| # | Invariant | Why it matters |
|---|---|---|
| **I6** | Release and cleanup operations are idempotent and safely retryable. | Pipeline retries are inevitable (network glitches, killed processes, operator re-runs). A non-idempotent operation that runs twice can corrupt state silently. |
| **I7** | A catalog version is not "active" until all required artifacts are validated and committed. | Without an explicit ACTIVE state, partially-published releases (blobs uploaded but Flutter not committed, etc.) are indistinguishable from complete ones. Consumers see inconsistent state. |
| **I8** | Cleanup may only execute against a validated `detail_index.json` (no missing hashes, no duplicates). | Orphan computation against a corrupted or partial index silently deletes blobs that are still referenced. Garbage in, mass deletion out. |
| **I9** | Only one release or cleanup operation may hold the pipeline release lock at a time. | Two concurrent releases can violate every other invariant simultaneously: one uploads blobs that the other deletes, registry rows interleave, indexes desynchronize. The single biggest operational hazard. |
| **I10** | Release validation derives from committed git state, never unstaged or local-only filesystem state. | Working-tree state is unreliable: dirty trees, wrong-branch commits (today's incident), detached HEAD, reverted-but-not-reset files, untracked artifacts. Trust must be anchored in git's committed history. |

---

## Decision

Adopt a phased redesign of the release pipeline that enforces all ten invariants (I1–I10). The design is split into seven phases (P1–P6 below, plus the already-completed P0 cherry-pick). Phases P1–P4 are approved for immediate execution. P5 and P6 are deferred until after the app reaches TestFlight / V1.0 release flow stability.

### Locked design decisions

1. **Bundle commit gating: Option β (gated-manual).** The pipeline refuses to mark a release complete until it observes a commit on the Flutter repo's `main` branch whose `assets/db/export_manifest.json` carries the new release's `db_version`. The operator runs the bundle-and-commit step manually; the pipeline mechanically verifies they did. **Auto-PR (Option α) is explicitly deferred** to a later phase — write access from the pipeline machine into the Flutter repo is an ops concern we will revisit when release cadence justifies it.

2. **Quarantine TTL: 30 days.** Soft-deleted blobs sit in `shared/quarantine/{date}/{shard}/{hash}.json` and are eligible for hard-delete by a separate tombstone-sweeper after 30 days. Recovery within the window is `mv` + manifest update.

3. **Release channels (initial set):** `bundled`, `ota_stable`, `dev`. `ota_beta` is **explicitly deferred** until a real beta cohort exists. Channel taxonomy lives in the `catalog_releases.release_channel` column (P3).

4. **Phase order:** P1 → P2 → P4 → P3. Rationale: P1+P2 close the immediate failure mode (gates + reversibility) without any new infrastructure. P4 adds an independent second-line defense in the Flutter repo — useful regardless of when P3 lands. P3 (registry) is the largest piece of infra and lands last so the gates and recovery mechanisms are battle-tested first.

5. **Repo locality:**
   - **Pipeline release safety** (gates, dry-run, quarantine, registry) lives in **`dsld_clean`**.
   - **`verify-bundle`** target and CI gate live in the **Flutter repo** (`PharmaGuide ai`). The pipeline may *invoke* the verifier, but the verifier itself belongs with the consumer.

6. **Cherry-picked bundle (`c706b4b`) stays on `main`.** This is the immediate workaround that unblocked the user; it is not subject to revision. The misplaced commit on `chore/pr-6a-decompose-interaction-warnings` will be cleaned up later (force-push, separately gated by user OK).

### Hard requirements (codified — these are pipeline-enforced, not aspirational)

| # | Requirement | Enforced by |
|---|---|---|
| HR-1 | No destructive cleanup may run in the same release unless all safety gates pass. | P1 |
| HR-2 | Cleanup must protect every catalog version that could still be used by installed apps, not just the latest. | P3 (P1 enforces single-version protection as interim) |
| HR-3 | Cleanup defaults to dry-run. Real execution requires `--execute`. | P1 |
| HR-4 | Large cleanup (deleting > N blobs or > N% of storage) requires explicit `--expected-count` confirmation that matches actual count. | P1 |
| HR-5 | Quarantined blobs are recoverable for 30 days. | P2 |
| HR-6 | Release logs record: protected versions, deletion candidates, quarantined blobs, skipped cleanup reasons, gate decisions. | P1 (logs), P3 (registry-derived protected set) |
| HR-7 | Flutter CI must verify bundled DB blob hashes resolve in Supabase before any release. | P4 |
| HR-8 | Until P1+P2 are landed and tested, no destructive orphan cleanup runs. | Operational freeze; enforced by the operator until P1+P2 ship. |
| HR-9 | Release and cleanup operations must be idempotent and safely retryable. | All phases (each phase's acceptance criteria includes a rerun test) |
| HR-10 | A release transitions to ACTIVE only after all activation preconditions pass (see "Release state machine" below). | P3 (state machine) + P1 (bundle alignment gate) + P4 (verify-bundle) compose the activation predicate |
| HR-11 | Cleanup may only execute against a validated `detail_index.json` (no missing hashes, no duplicates, manifest checksum matches). | P1 (precondition on candidate computation, before any gate evaluates) |
| HR-12 | Only one release or cleanup operation may hold the pipeline release lock at a time. | P1 (lock acquired before any state-mutating step; released on exit) |
| HR-13 | Release validation derives from committed git state, never unstaged or local-only filesystem state. | P1 (bundle-alignment gate reads from Flutter `main` HEAD, not working tree); cross-cutting principle for all later phases |

---

## Phases

### P1 — Bundle alignment gate + dry-run-by-default + structured cleanup logs

**Lives in:** `dsld_clean`
**Touches:** the orphan-cleanup script, `release_full.sh`'s call site, no schema changes

**Behavior:**

- **Pipeline release lock (HR-12):** First action of any state-mutating run. Implementation defaults to a lock file at `scripts/.release.lock` carrying PID + start timestamp + current step. If a stale lock is found (PID not running), prompt operator to clear; do not auto-clear. If a live lock is found, fail with the holder's metadata. Released on clean exit; trapped on signal handlers (`EXIT`, `INT`, `TERM`) to release on abort. Read-only operations (dry-run, audit-log queries) do not require the lock.

- **Detail-index validation (HR-11):** Before *any* gate computes, validate `dist/detail_index.json`:
  - Parses as JSON.
  - All blob entries have well-formed `sha256` keys (lowercase hex, length 64).
  - No duplicate hashes (a hash collision in the index is a pipeline bug, not a normal state).
  - The catalog DB SHA256 matches `export_manifest.json.checksum_sha256` (catches bit rot in the dist artifact itself).
  - Failure here is a hard error with no `--override` — a corrupted index is never safe to clean against.

- **Trust model (HR-13):** Gate inputs come from committed git state, not working tree. Specifically: bundle-alignment gate fetches `assets/db/export_manifest.json` from the Flutter repo's `main` HEAD (via `git show main:assets/db/export_manifest.json` against a local clone, or equivalent), not from the local Flutter checkout's working tree. Uncommitted Flutter changes are invisible to the pipeline by design.

- Cleanup CLI defaults to **dry-run mode**. Real execution requires `--execute`.
- Three hard gates evaluated before any deletion (even in `--execute` mode):
  - **Gate 1 — Bundle alignment:** Read `assets/db/export_manifest.json` from the Flutter repo's `main` branch HEAD (per HR-13); read `dist/export_manifest.json`. If `db_version` differs, fail with a message naming both versions and the remediation (`make bundle-and-commit` in Flutter repo, then re-run). Override flag: `--override-bundle-mismatch="<written reason>"`.
  - **Gate 2 — Blast-radius:** If `len(deletion_candidates) / len(in_storage) > 5%`, refuse to proceed unless `--expected-count=N` is passed AND equals the actual deletion count. (The 5% threshold is configurable; 5% is the default initial value, derived from typical incremental-build deltas; tune after observation.)
  - **Gate 3 — Live-version sanity:** If protected set is empty (no live catalog versions known), refuse all deletion.

   Until P3 lands, the "protected set" is the union of (a) blobs referenced by `dist/` and (b) blobs referenced by the Flutter repo's currently-bundled catalog on `main`. This is a degenerate-but-correct two-version protection that closes the failure mode while the registry is being built.

- **Idempotency (HR-9):** Two consecutive dry-runs against the same dist/ + Flutter `main` HEAD must produce byte-identical output (modulo timestamps in the audit log header). An interrupted `--execute` run, restarted, must converge to the same end state without double-deletion or duplicate audit rows.

- **Structured logging** (JSON-lines, written to `reports/release_audit/{timestamp}_{release_id}.jsonl`):
  - Decision events: `gate_passed`, `gate_failed`, `dry_run_started`, `execute_confirmed`, `lock_acquired`, `lock_released`, `index_validated`, `index_validation_failed`
  - State snapshots: `protected_versions`, `protected_blob_count`, `in_storage_count`, `candidates_count`, `would_delete_pct`
  - Per-blob decisions are *not* logged (volume); summary clusters by shard/category instead

- **Dry-run output is the artifact** — even on runs that proceed to `--execute`, the dry-run summary is captured and referenced by the audit trail. The operator can read what was *about* to happen on any historical run.

**Acceptance criteria:**
- Replaying the 2026-05-12 14:49 conditions (bundled = `v2026.05.11.164208`, dist = `v2026.05.12.203133`) must trigger Gate 1 failure with no deletions.
- Replaying with bundled = dist must succeed (gate passes).
- Default invocation with no flags produces a dry-run summary and exits 0 without touching storage.
- **Lock contention:** A second invocation while one is running must fail immediately with a message naming the current holder (PID, start time, current step). No silent block, no overwrite.
- **Idempotency:** Two consecutive dry-runs against unchanged inputs produce byte-identical candidate sets and identical state-snapshot fields in the audit log.
- **Index validation:** Cleanup against a `detail_index.json` with intentionally-corrupted JSON, a missing required hash field, or a hash-checksum mismatch must fail at the validation step with no gate evaluated and no candidate set computed.
- **Trust-model regression:** A Flutter working tree with an uncommitted `export_manifest.json` change must NOT influence the bundle-alignment gate. The gate must report based on the committed `main` HEAD only.

### P2 — Quarantine pattern (move-to-quarantine, 30d TTL, tombstone sweeper)

**Lives in:** `dsld_clean`
**Touches:** the orphan-cleanup script (replaces `DELETE` with `MOVE`), new `scripts/sweep_quarantine.py`

**Behavior:**

- `--execute` mode no longer hard-deletes. It moves blobs:
  ```
  shared/details/sha256/aa/aabbcc...json
        ↓
  shared/quarantine/2026-05-12/aa/aabbcc...json
  ```
  The date prefix (`2026-05-12`) is the cleanup-run date, not the original blob date. This preserves the original shard structure underneath, so a blob can be restored with a single `MOVE` back to `shared/details/sha256/aa/aabbcc...json`.

- **Idempotent MOVE (HR-9):** Re-running quarantine on a blob already in `shared/quarantine/{date}/{shard}/{hash}.json` is a no-op. Specifically: if the source `shared/details/sha256/{shard}/{hash}.json` does not exist (already moved) AND the quarantine target exists, skip with an audit log entry `quarantine_skipped_already_done`. If the source exists AND a quarantine target exists at a different date prefix (a prior quarantine run), the new quarantine path supersedes — the older quarantine copy is deleted (it was about to be tombstoned anyway). The MOVE is implemented as `COPY` + verify-checksum + `DELETE source`, never as a single non-atomic operation.

- **`scripts/sweep_quarantine.py`** runs on an explicit cadence (operator-invoked initially; cron-able later). It hard-deletes anything in `shared/quarantine/{date}/` where `date < today - 30d`. It also defaults to dry-run; `--execute` required for real deletion. Sweeper is idempotent: re-running after a partial completion picks up where it left off without re-deleting already-deleted blobs (404s on the storage API are treated as success).

- **Recovery procedure** (documented in operations runbook):
  ```
  python scripts/recover_quarantined_blob.py <sha256_hash>
  # → finds the blob in shared/quarantine/*/
  # → copies it back to shared/details/sha256/{shard}/{hash}.json
  # → emits an audit log entry
  ```
  Recovery is also idempotent: running it on an already-recovered blob is a no-op.

- **Storage cost note:** quarantine adds storage usage. Estimated impact at current scale (8,331 active blobs, typical incremental delta < 5% per release, ~3 KB/blob average): adding ~30 days of quarantine retains roughly 1.5–2× the active blob count in storage. Acceptable for the recovery guarantee; revisit if scale changes by an order of magnitude.

**Acceptance criteria:**
- A blob "deleted" by cleanup must be retrievable via `recover_quarantined_blob.py` for 30 days after.
- After 30 days + 1 day, the sweeper hard-deletes it; recovery is no longer possible (this is the intended TTL behavior).
- Quarantine path layout preserves shard prefix (so recovery is a clean inverse `MOVE`, no metadata reconstruction).
- **Idempotency:** Re-running cleanup `--execute` on an already-quarantined blob produces no errors, no duplicate quarantine entries, and an audit log entry indicating "already quarantined."
- **Sweeper idempotency:** A sweeper run interrupted mid-batch, re-run, must complete without errors and without attempting to delete blobs already gone.
- **Atomicity of MOVE:** Forced failure between COPY and DELETE source must leave the blob retrievable from EITHER the source OR the quarantine path (never disappeared). The next cleanup run reconciles.

### P4 — Flutter `verify-bundle` target + CI gate

**Lives in:** `PharmaGuide ai`
**Touches:** new `make verify-bundle` target, new `scripts/verify_bundle.dart` (or shell+sqlite3+curl, whichever is simpler), CI workflow update

**Behavior:**

- `make verify-bundle`:
  1. Reads `assets/db/export_manifest.json` → captures `db_version` and `checksum_sha256`.
  2. SHA256s `assets/db/pharmaguide_core.db` → asserts it matches `checksum_sha256`. (Catches local file corruption before doing any network work.)
  3. Selects 20 random products from `products_core` (deterministic seed = `db_version` so runs are reproducible).
  4. For each: fetches its `detail_blob_sha256` from Supabase storage (`shared/details/sha256/{shard}/{hash}.json`) using the public anon key.
  5. Asserts: HTTP 200, JSON parses, has expected top-level keys (`dsld_id`, `ingredients`, `warnings`).
  6. Exits 0 on all-pass; exits non-zero with a structured failure summary on any failure.

- **CI gate:** A GitHub Action job that runs `make verify-bundle` on any PR that modifies `assets/db/`. Required for merge to `main`. (CI infra decision — workflow file location and runner image — to be made when P4 is implemented; not pre-locked here.)

- **Flutter Makefile addition** (concept; exact wiring at implementation time):
  ```make
  verify-bundle:
      @dart run scripts/verify_bundle.dart \
          --manifest assets/db/export_manifest.json \
          --db assets/db/pharmaguide_core.db \
          --supabase-url $$SUPABASE_URL \
          --anon-key $$SUPABASE_ANON_KEY \
          --sample-size 20
  ```

**Acceptance criteria:**
- Replaying the 2026-05-12 incident: `make verify-bundle` against the stale `v2026.05.11.164208` bundle must fail (with the missing-blob 404s as the failure reason).
- Against the cherry-picked `v2026.05.12.203133` bundle, must pass.
- Sample size of 20 is the initial value — small enough to run in seconds, large enough to catch systematic breakage with high probability. Reviewable.
- **Idempotency:** Two consecutive runs against the same bundle + Supabase storage produce identical pass/fail verdict and identical sample set (deterministic seed).

### P3 — Catalog release registry + protected-blob-set computation

**Lives in:** `dsld_clean`
**Touches:** pipeline manifest schema (new table), orphan-cleanup script (replaces P1's degenerate two-version protection with the proper union), release_full.sh (writes registry rows on every release)

**Behavior:**

- **New table `catalog_releases`** (lives in the same Postgres/SQLite that backs the manifest table — exact home decided at implementation):

  ```sql
  CREATE TABLE catalog_releases (
    db_version              TEXT PRIMARY KEY,
    state                   TEXT NOT NULL CHECK (state IN ('PENDING','VALIDATING','ACTIVE','RETIRED')),
    released_at             TIMESTAMPTZ NOT NULL,
    activated_at            TIMESTAMPTZ,                 -- set when state -> ACTIVE
    retired_at              TIMESTAMPTZ,                 -- set when state -> RETIRED
    release_channel         TEXT NOT NULL CHECK (release_channel IN ('bundled', 'ota_stable', 'dev')),
    bundled_in_app_versions TEXT[],                      -- e.g. '{1.0.0, 1.0.1}'
    flutter_repo_commit     TEXT,                        -- SHA of the Flutter bundle commit on main
    detail_index_url        TEXT,                        -- pointer to the archived detail_index.json for this version
    notes                   TEXT
  );
  ```

  A version is **live iff `state = 'ACTIVE'`**. Retirement is an explicit operator action (e.g., `python scripts/retire_release.py 2026.05.10.132843 --reason "deprecated TestFlight build"`), recorded in the audit trail. See "Release state machine" below for full state semantics.

- **Duplicate registration handling (HR-9):** `INSERT` on existing `db_version` is a no-op (`INSERT ... ON CONFLICT DO NOTHING`), not an error. Re-running release registration after a partial failure converges; never errors on "already registered." State *transitions* (e.g., re-activating an already-ACTIVE version) are also no-ops.

- **Protected-set computation** (replaces P1's bundled∪dist heuristic):
  ```python
  def compute_protected_blobs() -> set[str]:
      live = db.fetch("SELECT db_version, detail_index_url FROM catalog_releases WHERE state = 'ACTIVE'")
      protected = set()
      for v in live:
          index = fetch_detail_index(v.detail_index_url)
          # HR-11: validate before use
          assert_valid_detail_index(index)
          protected.update(index['blobs'].keys())
      return protected
  ```

- **Release entry creation** is part of `release_full.sh` — every release that successfully publishes (passes all gates, commits to Flutter, etc.) inserts a new `catalog_releases` row in `state='PENDING'` with `release_channel='dev'` initially. Promotion to `state='ACTIVE'` happens only when all activation preconditions pass (see state machine). Channel promotion (`dev` → `bundled` → `ota_stable`) is independent of the state transition and represents which consumers are pointed at this version.

- **Backfill:** when P3 lands, the registry must be backfilled with at least the currently-bundled catalog (`v2026.05.12.203133` as of this ADR, marked `state='ACTIVE'`, `release_channel='bundled'`) and any catalog versions still served via OTA.

**Acceptance criteria:**
- `compute_protected_blobs()` returns the union of all ACTIVE versions' blob refs.
- Cleanup cannot proceed if it would delete blobs in the protected set (regression test on the 2026-05-12 scenario must hold).
- Retiring a version transitions it to `state='RETIRED'`; its blobs leave the protected set on the next cleanup run; the next sweep then becomes eligible to quarantine those blobs.
- **Idempotency:** Running release registration twice on the same `db_version` produces a single row, no errors, no duplicate audit log entries.
- **State machine queryable:** The activation predicate (PENDING/VALIDATING → ACTIVE conditions) is implementable as a SQL function or query that the pipeline can evaluate transactionally (no partial-active intermediate visible to consumers).

---

## Release state machine (HR-10)

A catalog version progresses through explicit states. Cleanup, OTA, and consumer-facing systems treat only ACTIVE versions as live.

```
PENDING ─→ VALIDATING ─→ ACTIVE ─→ RETIRED
              │  ↑             (one-way from ACTIVE; no re-activation)
              ↓  │
            (any failure → back to PENDING; the version is never partially-active)
```

**State semantics:**

- **PENDING** — the row exists in `catalog_releases` but no activation work has started (or the most recent activation attempt failed and rolled back). Not visible to consumers. Blobs are not protected.
- **VALIDATING** — activation in progress. Blobs uploaded; checksums being verified; Flutter bundle commit being looked for. Not visible to consumers. Blobs are *protected* during this transient state to prevent in-flight cleanup from deleting them.
- **ACTIVE** — fully validated and live. Visible to consumers (via channel routing). Blobs are protected.
- **RETIRED** — explicitly retired by operator action. No longer visible to consumers. Blobs no longer protected (eligible for cleanup → quarantine → tombstone).

A version transitions to **ACTIVE** only after all of the following pass, atomically (any failure leaves the version in PENDING with the failure recorded):

1. **Blob upload completes.** Every hash in this version's `detail_index.json` resolves to a non-empty object in `shared/details/sha256/{shard}/{hash}.json`.
2. **Manifest checksum validates.** The catalog DB SHA256 matches `export_manifest.json.checksum_sha256`.
3. **Flutter bundled catalog verification passes.** `make verify-bundle` against the Flutter repo's `main` HEAD returns 0 for this `db_version` (P4 gate).
4. **Release registry row is committed.** A row exists in `catalog_releases` with this `db_version`, `state='ACTIVE'`, `activated_at` set, and `flutter_repo_commit` populated with the SHA of the Flutter bundle commit.

The activation predicate is a single transactional check — the version is either ACTIVE or it is not. There is no partial-active state visible to consumers.

**Retirement** is a one-way transition: ACTIVE → RETIRED, performed by an explicit operator action. RETIRED versions are no longer protected by cleanup and their blobs become deletion candidates on the next sweep. Re-activation of a retired version is not supported (publish a new version instead).

---

## Concurrency model (HR-9, HR-12)

Pipeline operations that mutate shared state — releases, cleanups, registry retirements, quarantine sweeps — must acquire a single global pipeline lock before proceeding. Operations that only read state (dry-run cleanup, audit-log queries, `verify-bundle`) do not require the lock.

**Implementation options** (decided at P1 implementation, not pre-locked here):

- Lock file in a known shared location (`scripts/.release.lock`) — simplest, works for single-machine pipeline. Default for P1.
- Postgres advisory lock — works across machines. Switch when pipeline runs distributed.
- Supabase storage object as mutex (atomic create-with-precondition) — works for any pipeline machine with Supabase access.

The choice depends on whether the pipeline ever runs on more than one machine. Currently single-machine, so a lock file with stale-detection (PID + timestamp) is sufficient. Revisit if/when the pipeline runs distributed.

**Lock semantics:**
- Acquired at start of `release_full.sh` (and any other state-mutating entry point: `cleanup_orphan_blobs.py --execute`, `sweep_quarantine.py --execute`, `retire_release.py`).
- Released on clean exit OR on operator-confirmed cleanup of a stale lock.
- Stale detection: if lock holder PID is not running, prompt operator to clear; do not auto-clear (prevents accidental clobbering when an operator has paused the lock-holder process).
- Failure to acquire is a hard error with a message naming the current holder (PID, start time, current step).
- Trapped on signal handlers (`EXIT`, `INT`, `TERM`) to release on abort. Crashes that bypass signal handlers leave a stale lock — operator clears explicitly.

---

## Trust model (HR-13)

**All release validation derives from committed git state.** Working-tree state, untracked files, and local-only filesystem state are not authoritative for any gate.

Concrete consequences:

- Bundle-alignment gate (P1) reads `assets/db/export_manifest.json` from the Flutter repo's **committed `main` HEAD**, not from the working tree. If the operator has uncommitted bundle changes locally, the gate ignores them.
- `verify-bundle` (P4) operates on the bundle as it appears in the commit being verified — it does not trust uncommitted changes, even if they would pass.
- Release registry rows (P3) record the `flutter_repo_commit` SHA — a specific commit, not "current main." If main moves after the release row is written, the row still references the historical SHA.

This protects against: detached HEAD, dirty working tree, wrong-branch commits (today's incident), reverted-but-not-reset working trees, untracked bundle artifacts.

**The single exception:** P1 reads `dist/` from the local filesystem because dist/ is the pipeline's *output*, not its *input*. dist/ does not need to be committed — it needs to be self-consistent (manifest checksum matches DB, validated per HR-11). The "committed-only" rule applies to anything that crosses the pipeline → consumer boundary.

---

## Rollback playbook

When a published release proves bad (corrupted data, regression, contract violation), rollback follows this procedure. Detailed runbook lives in `docs/PIPELINE_OPERATIONS_README.md` rollback section (added during P3 implementation).

```
1. Mark the bad release retired.
   python scripts/retire_release.py <bad_db_version> --reason "<one-line cause>"
   → sets catalog_releases.state = 'RETIRED', retired_at = now() for this version
   → bad version is no longer in the protected blob set
   → bad version no longer eligible for OTA delivery

2. Restore the previous catalog as active in Flutter.
   git revert <bundle commit on Flutter main>      # OR cherry-pick the prior bundle commit
   → assets/db/ on Flutter main now points at the previous version
   → next OTA / app reinstall picks up the prior catalog
   → if the prior version was already RETIRED in step 1's neighborhood, transition it back via:
     python scripts/reactivate_release.py <prior_db_version> --reason "rollback target"
     (re-activation is the ONE retirement-reverse case the system allows; operator must justify)

3. Restore quarantined blobs if the previous version's blobs were swept.
   for hash in $(diff_protected_blobs <prior_db_version> <bad_db_version>):
       python scripts/recover_quarantined_blob.py "$hash"
   → quarantined blobs return to shared/details/sha256/{shard}/
   → only works within the 30-day quarantine TTL
   → blobs already hard-deleted by the tombstone sweeper cannot be recovered;
     in that case, the only path is to republish the prior version (re-run pipeline from prior dataset state)

4. Invalidate OTA pointers (if OTA delivery is active).
   python scripts/invalidate_ota_manifest.py <bad_db_version>
   → ensures running apps don't pick up the bad version on next OTA check
   → forces them to the most recent ACTIVE prior version

5. Re-run verify-bundle against the restored state.
   cd "/Users/seancheick/PharmaGuide ai" && make verify-bundle
   → must exit 0 before declaring rollback complete
   → failure here means the rollback is itself broken; treat as a fresh incident (P0)
```

**Constraints:**
- Steps 1–4 must complete in order. Skipping or re-ordering steps risks leaving consumers in an inconsistent state (e.g., running an app that fetches blobs that were never restored).
- Rollback acquires the pipeline release lock (HR-12). No release or cleanup can run concurrently with rollback.
- Rollback writes to the audit log with `event_type='rollback'` and a reason; the log captures every step's outcome.

**Time-bounds:**
- Steps 1–2 are immediate (operator action + git operation).
- Step 3 is bounded by quarantine TTL; outside the 30-day window, recovery is not possible. After 30d, the only path is to republish the prior version.
- Step 4 is bounded by OTA propagation delay (usually < 1 hour, but depends on app refresh cadence).
- Step 5 is the verification gate.

If step 5 fails, do not declare rollback complete. The system is in a worse state than before rollback started; treat as a P0 incident.

---

## Considered alternatives

### Heuristic retention ("retain last N catalog versions")

Initially proposed as "B1" in the design discussion. Rejected because:
- "Last N" is a guess, not a guarantee. If the operator rebuilds the pipeline 5 times in an hour for testing, "last 3" silently rotates out genuinely-bundled versions.
- Doesn't survive operator workflow variance. P3's explicit registry replaces guess with declared state.

### Option α — auto-PR for the Flutter bundle commit

Proposed and explicitly **deferred**. Rationale:
- Requires the pipeline machine to have Flutter-repo write access (SSH key or GitHub App), which is a meaningful ops surface.
- Option β (gated-manual) closes the failure mode equally well — the bundle either lands on `main` or the release fails. The auto-PR ergonomics are nice but not on the critical path.
- Will reconsider when release cadence increases (post-V1.0). At that point, the auto-PR mechanism can be added without changing the gates.

### Bundle as a pipeline-internal artifact (skip the Flutter repo entirely)

Considered: serve the bundle directly from Supabase, skip the bundled-in-app DB. Rejected because:
- The Flutter app needs an offline-first catalog at install time. Network-only is not consistent with the product requirement (`pharmaguide_core.db — read-only, 180K products, 88 cols, replaced via OTA`).
- OTA delivery already exists for incremental updates; the bundled DB is the install-time seed. The architecture is correct; only the consistency between bundled DB and Supabase storage is the bug.

---

## Consequences

### Positive

- The 2026-05-12 failure mode becomes mechanically impossible (P1 gate).
- Mistakes are recoverable for 30 days (P2 quarantine).
- An independent second-line check exists in the Flutter repo (P4).
- "What was the state of storage on date X?" is answerable from registry + audit logs (P3 + structured logs).
- Operator workflow lapses (forgetting to commit, committing to wrong branch) cannot silently corrupt state.
- Concurrent pipeline runs cannot interleave (HR-12 lock).
- Partial releases never appear "live" to consumers (HR-10 state machine).

### Negative / costs

- Storage usage grows by quarantine retention (~1.5–2× active blob count). Acceptable at current scale.
- Each release now requires the Flutter bundle commit to land on `main` before cleanup runs. Adds one mechanical step to the operator workflow (but eliminates a class of silent failures).
- P3 registry adds a small schema-migration burden — needs a one-time backfill on landing.
- `verify-bundle` adds CI time to PRs touching `assets/db/` (estimated: < 30s for a 20-product sample).
- Pipeline release lock serializes operations — concurrent runs fail-fast rather than queue. Operator must wait or kill the prior run; not a problem at current cadence.

### Operational

- **Until P1+P2 land, no destructive orphan cleanup runs.** The operator should pass `--skip-cleanup` (or equivalent — exact flag at implementation) when running `release_full.sh` or invoke the snapshot/upload steps individually. Storage will grow during this freeze; that is acceptable for the duration.
- `release_full.sh`'s "Next steps" footer becomes obsolete once P1's gates land — the manual reminder is replaced by mechanical enforcement.
- Stale lock cleanup is a manual operator action (no auto-clear). Document the procedure in `PIPELINE_OPERATIONS_README.md` alongside the runbook.

---

## Explicitly deferred (NOT in this ADR's scope)

- **P5: Bundle commit automation (Option α auto-PR).** Revisit post-TestFlight.
- **P6: Release audit table + dashboard query.** Deferred — P1's structured logs are sufficient for the immediate failure-mode diagnostic. A queryable dashboard is observability polish, not safety.
- **`ota_beta` channel.** Add to the `release_channel` CHECK constraint when a real beta cohort exists.
- **Distributed pipeline lock** (Postgres advisory or Supabase mutex). Lock file is sufficient for single-machine pipeline. Switch when distributed.
- **Cleanup of `chore/pr-6a-decompose-interaction-warnings`** (the misplaced bundle commit). Force-push on a pushed branch needs separate operator approval; not part of this design.

---

## Open questions (to resolve at implementation time, not now)

- **CI runner image** for `make verify-bundle` — needs Dart + curl + sqlite3. Decided at P4 implementation.
- **`catalog_releases` table home** — same DB as existing manifest table, or new schema? Decided at P3 implementation.
- **Tombstone sweeper cadence** — operator-invoked initially. Cron-able later if operational load justifies.
- **`recover_quarantined_blob.py`** access control — currently any operator with pipeline access can recover. Tighten if/when needed.
- **Lock file vs Postgres advisory lock** — start with lock file; revisit if pipeline goes distributed.
- **`reactivate_release.py`** — does the rollback re-activation path need a stronger gate (e.g., second operator approval)? Decided at P3 implementation.

---

## Implementation order (locked)

```
P0 ─── Cherry-pick bundle commit onto main ─── DONE (c706b4b on 2026-05-12)
                ↓
P1 ─── Bundle alignment gate + dry-run + structured logs ─── NEXT
       (also: lock + index validation + trust model + idempotency)
                ↓
P2 ─── Quarantine pattern + 30d TTL + sweeper
       (also: idempotent MOVE + atomic COPY-then-DELETE)
                ↓
P4 ─── Flutter verify-bundle + CI gate
                ↓
P3 ─── catalog_releases registry + protected-set + state machine
                ↓
[Resume destructive cleanup with all gates active]
                ↓
[Defer P5 / P6 to post-TestFlight]
```

No phase ships without acceptance criteria passing. No destructive cleanup runs in production until P1+P2 are landed and the regression test (replay of 2026-05-12) passes.

---

## Phase status — implementation log (as of 2026-05-13)

P1, P2, P4, and P3 are all complete. The pipeline now enforces every
invariant (I1–I10) and every hard requirement (HR-1 through HR-13) listed
above. Acceptance criteria for each phase passed before commit; the
2026-05-12 incident class is now closed by construction.

### P1 — Bundle alignment + dry-run + structured logs ✅ COMPLETE

| Sub-phase | Module | Commit |
|---|---|---|
| P1.0 | `--allow-destructive-orphan-cleanup` opt-in default OFF in `sync_to_supabase.py` | (sprint commits) |
| P1.1 | `release_safety/lock.py` — pipeline release lock, signal trap, PID liveness | `78f5732` |
| P1.2 | `release_safety/index_validator.py` — `detail_index.json` validator | `8246bd4` |
| P1.3 | `release_safety/bundle_alignment.py` — Flutter `main` HEAD bundle gate | `2ddb348` |
| P1.4 | `release_safety/protected_blobs.py` — bundled∪dist interim union | `cb229a4` |
| P1.5a | `release_safety/audit_log.py` — append-only JSONL, fsynced | `9051441` |
| P1.5b | `release_safety/gates.py` — 3-gate orchestrator with aggregating failures | `8966dc4` |
| P1.6 commit 1 | `cleanup_orphan_blobs_with_gates()` in `cleanup_old_versions.py` | (sprint) |

### P2 — Quarantine + 30d TTL + sweeper ✅ COMPLETE

| Sub-phase | Module | Commit |
|---|---|---|
| P2.1a | `release_safety/quarantine.py` — COPY+verify+DELETE move-to-quarantine | `f5c1778` |
| P2.1b | `release_safety/quarantine_sweeper.py` — TTL-based hard-delete | `d86ba40` |
| P2.2 | Wire quarantine into `cleanup_orphan_blobs_with_gates` (replaces hard-delete) | (sprint) |

### P4 — Flutter `verify-bundle` + CI gate ✅ COMPLETE

| Sub-phase | Module | Commit |
|---|---|---|
| P4.1 | `scripts/verify_bundle.dart` in PharmaGuide repo | `f9dcc6f` (Flutter) |
| P4.2 | `.github/workflows/verify-bundle.yml` CI gate | `61d2851` (Flutter) |

### P3 — Catalog release registry ✅ COMPLETE

| Sub-phase | Module / change | Commit |
|---|---|---|
| P3.1 | `catalog_releases` schema in `supabase_schema.sql` + 8 contract tests | `c5da5f2` |
| P3.1 | Live migration `p3_1_catalog_releases_registry` applied to Supabase | (MCP `apply_migration`) |
| P3.2 | `release_safety/registry.py` — Python API + strict state machine + 42 tests | `edcd137` |
| P3.3 | `release_safety/backfill_catalog_releases.py` + 19 tests | `d25b08e` |
| P3.3 | Live `--execute` of backfill — 2 ACTIVE rows inserted | (operator action) |
| P3.4 | `release_safety/retire_release.py` CLI + audit + 21 tests | `2206b47` |
| P3.5 | `protected_blobs.compute_protected_blob_set` extended to bundled∪dist∪registry + 11 tests | `abd0705` |
| P3.6a | `cleanup_old_versions.py` passes `supabase_client` through; integration test | `7f47403` |
| P3.6b | `sync_to_supabase.py` auto-walks PENDING→VALIDATING→ACTIVE around manifest flip + 15 tests | `3fc4f13` |

### Storage cleanup operations log

| Date | Action | Commit |
|---|---|---|
| 2026-05-13 | Bucket 2 cleanup — 515.36 MiB of stale version-dirs reclaimed | `d14673c` |
| 2026-05-13 | Storage audit module (read-only inventory) | `ee3e6fe` |

### Test coverage

- 325 tests pass across release-safety + schema-contract + sync + cleanup suites.
- All sign-off acceptance criteria for P1, P2, P3, P4 pass.
- 2026-05-12 incident regression test: a replay of bundled=`v2026.05.11.164208` + dist=`v2026.05.12.203133` triggers Gate 1 failure with zero deletions.

### Still pending (post-P3)

- **P1.6 commit 2 (next):** flip orphan-cleanup default to ON. Gates + quarantine + registry-backed protection are all in place, so the freeze can lift.
- **Operator tasks:** Supabase Pro upgrade before 2026-05-25 storage cutoff; verify-bundle CI secrets; iPhone product-detail smoke test post-cleanup.
- **Deferred:** drop `dist_dir` parameter from `compute_protected_blob_set` after one clean release cycle observed end-to-end with P3.6b.
- **P5/P6:** still deferred until post-TestFlight per the original ADR.
