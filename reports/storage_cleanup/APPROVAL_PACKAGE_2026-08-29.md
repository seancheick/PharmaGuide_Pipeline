# Storage Maintenance — Consolidated Approval Package (2026-08-29)

Everything below was measured live and read-only on 2026-08-29, or proven by
tests on branch `codex/storage-maintenance-final`. **Nothing irreversible has
run.** Three production actions await approval; each is executable
independently.

## Current verified state

| Area | Live state |
|---|---:|
| Active detail blobs | 16,528 / 3,558,214,275 B |
| Current orphans | 0 |
| Quarantine 2026-07-17 | 18,391 / 2,375,048,433 B — TTL-eligible NOW |
| Quarantine 2026-08-06 | 963 / 229,699,017 B — eligible Sep 6 |
| Quarantine 2026-08-28 | 118,947 / 21,933,347,321 B — eligible Sep 28 |
| Stale version dirs | 9 / 1,288 objects / 203,784,968 B |
| Storage-inventory RPC | authored, NOT applied |

## What changed in code (committed this branch, all tested)

1. **Sweep decoupled from releases.** `cleanup_old_versions --execute` (run by
   every catalog release) no longer hard-deletes expired quarantine — it
   reports eligible work as DEFERRED and points at the gated CLI. The 08-27
   release's unattended partial sweep can never recur.
2. **Gated sweeper CLI** (`scripts/sweep_quarantine.py`): dry-run approval
   artifact (dates, counts, bytes, eTag coverage, path list, fingerprint);
   execute requires artifact + count + bytes + fingerprint, holds the release
   lock, refuses drifted sets/pre-TTL dates/edited artifacts, refuses if a
   protected hash's ONLY copy sits in quarantine, deletes 500/batch,
   checkpoints per shard, counts only listing-proven absence.
3. **Manifest rows die only after storage is proven empty.** Version cleanup
   now enumerates recursively (raising on listing failure), batch-deletes,
   re-lists as the absence proof, and keeps the row on ANY partial work so the
   next run resumes. Storage-driven reconciliation surfaces manifest-less
   dirs every run. The stale-dir executor's manifest-race recheck moved
   INSIDE the release lock and gained per-directory absence proofs.
4. **Churn root cause fixed** (one word): `blends[].sources` was emitted as
   `list(set(...))` — PYTHONHASHSEED ordering reaching the content-addressed
   blob. Probe: 24/25 sampled "changed" blobs differed only in that list's
   order. Fix `sorted()`; consumer proof: zero Flutter readers of the field;
   output multiset-identical. Effective from the NEXT catalog build — expect
   changed blobs to drop from ~1,192/release toward ~130 genuinely semantic.

## July-count discrepancy — resolved from artifacts

`reports/storage_cleanup/july_quarantine_forensics_2026-08-29.json`.
The earlier "~31,200" figure exists in no artifact and is retracted. Proven:
the 2026-07-17 run quarantined **42,418** (audit 20260717T203015Z, blast gate
expected==actual). TTL crossed Aug 16; sweeps were silent no-ops until the
2026-08-26 sweeper fix; the **2026-08-27 release's automatic sweep**
hard-deleted **24,027** unattended. Survivors (18,391) sit in contiguous
shard bands (00..4c empty, 4d..bd populated, be..ff empty) — the signature of
that sweeper's sequential walk skipping listing-failed shards; July's
parallel move engine cannot produce contiguous bands. TTL-compliant, but
exactly the unattended hazard item 1 removes.

## The three production actions awaiting approval

### (A) July quarantine hard-delete — IRREVERSIBLE
Artifact: `sweep_approval_2026-08-29.json` · **18,391 objects /
2,375,048,433 bytes** · fingerprint `2461730acb2034eeff46bc836f246b5447b18785511175c7c0636a4f87cd461e`
```bash
cd /Users/seancheick/Downloads/dsld_clean && source scripts/python_env.sh && "$PG_PYTHON" scripts/sweep_quarantine.py --execute --approval-report reports/storage_cleanup/sweep_approval_2026-08-29.json --expected-count 18391 --expected-bytes 2375048433 --fingerprint 2461730acb2034eeff46bc836f246b5447b18785511175c7c0636a4f87cd461e --flutter-repo "/Users/seancheick/PharmaGuide ai" --dist-dir scripts/dist --result-out reports/storage_cleanup/sweep_result_2026-08-29.json
```
Watched run; post-verified to zero by re-listing. Aug-06 and Aug-28 batches
are structurally untouchable before their dates.

### (B) Stale version directories — quarantine-less delete of dead artifacts
Plan: `stale_dirs_plan_2026-08-29.json` · **9 dirs / 1,288 objects /
203,784,968 bytes** (list in the plan; both retained versions excluded).
Executes via the hardened `delete_stale_version_dirs` (count+bytes approval,
manifest recheck under lock, per-dir absence proof).

### (C) Storage-inventory RPC migration
`migrations/20260828120000_storage_inventory_rpc.sql`, SHA-256
`43fabd7825ced3c781d851ec223ac435557fd482b510895a9f3b427f8901f87c`.
EXPLAIN already proves the index range scan (16,528 rows, no seq scan).
Post-apply: migration-history repair to version `20260828120000`, permission
denial proofs (anon/authenticated), 3× locked walker-vs-RPC parity, advisors.
Full runbook: `rpc_rollout_prep_2026-08-29.md`. Walker remains the authority;
flag stays default-off.

## Recovery and rollback boundaries

- (A) is the point of no return for July's 2.21 GiB — already 13 days past
  its recovery window. (B) deletes dead version artifacts referenced by no
  manifest row, registry row, or index. (C) is read-only SQL, revertible by
  DROP FUNCTION + history-row removal.
- Aug-28's 20.43 GiB stays recoverable until Sep 28; storage usage falls
  materially only after that batch is swept (next eligible dates: Sep 6 —
  963 objects; Sep 28 — 118,947).

## Test evidence

- Storage-focused slice: 542 passed (engine, sweeper CLI, manifest safety,
  stale-dir hardening, RPC client, benchmark, recovery).
- `scripts/test.sh fast` and `scripts/test.sh release`: recorded in the
  final report alongside this package.
