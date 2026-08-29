# Storage Maintenance — Consolidated Approval Package v2 (2026-08-29)

Supersedes `APPROVAL_PACKAGE_2026-08-29.md`. All four review gaps are closed;
every number below is a fresh live measurement or an exact full-population
count. **Nothing irreversible has run.** Recommended execution order per
review: **(C) RPC → fresh fast inventory → (B) stale dirs → (A) July sweep.**

## Gap closures (all RED→GREEN tested, mutation-checked where noted)

1. **Sweep identity binds (path, size, eTag).** The artifact stores a full
   record per object; the fingerprint digests the sorted records; execute
   re-inventories under the lock and refuses the run on ANY same-path
   size/eTag drift. Path grammar + shard/hash agreement enforced; execute
   `--ttl-days` must equal the artifact's; TTL < 30 days refused everywhere.
   (The test fixture's name-derived eTag was itself hiding drift — now
   content-MD5 like the live API.)
2. **Stale-dir execution binds to the reviewed artifact.** `plan_to_artifact`
   emits every version/path/size + retained-manifest digest + fingerprint
   over (version, path, size) records; `execute_from_artifact` requires the
   quad, and inside ONE lock hold recomputes the fresh plan and requires
   fingerprint equality — a swapped candidate with identical totals refuses
   (pinned by test), then manifest recheck + per-dir absence proofs run.
3. **Churn proof is full-population, no extrapolation.** All 1,192 changed
   pairs classified, 0 errors: **1,044 sources-order-only / 0 other-order-only
   / 148 genuinely semantic**. Avoidable bytes, exact: **453,761,407**;
   semantic bytes: 86,402,112 (evidence/confidence/dose fields — that
   release's real work). First-pass JSON marked SUPERSEDED with its
   contradiction explained. The determinism test now drives the REAL
   `_merge_blend_evidence` under PYTHONHASHSEED 0/1/42/31337
   (mutation-checked). The ~1,192→~148 reduction is **projected** until the
   next ordinary rebuild measures it.
4. **RPC migration re-versioned forward** to `20260830090000` (ahead of live
   head `20260829151221`) — applying it needs NO history editing; misalignment
   falls back to the documented `supabase migration repair`, never table
   surgery. This repo's `migrations/` is the canonical owner. New SHA-256:
   `74ba616ca6144af9ca05c51c8ddc62f5190259b8e29879da1eed5af40baa794a`.

## Current live state (measured this pass)

| Area | Live state |
|---|---:|
| Active detail blobs | 16,528 / 3,558,214,275 B |
| Current orphans | 0 |
| Quarantine 2026-07-17 | 18,391 / 2,375,048,433 B — TTL-eligible NOW |
| Quarantine 2026-08-06 | 963 / 229,699,017 B — eligible Sep 6 |
| Quarantine 2026-08-28 | 118,947 / 21,933,347,321 B — eligible Sep 28 |
| Stale version dirs | 9 / 1,288 / 203,784,968 B |

## The three production actions (fresh artifacts, exact commands)

### (C) RPC migration — recommended FIRST (fully reversible)
Apply `migrations/20260830090000_storage_inventory_rpc.sql` (SHA-256
`74ba616c…`) under version `20260830090000`; verify the migration listing
shows exactly that version; then permissions proof, prefix-refusal probe,
3× `--verify-inventory` parity, fallback probe, advisors — full runbook in
`rpc_rollout_prep_2026-08-29.md`. Flag stays default-off; walker stays the
authority. Then run one fresh fast inventory.

### (B) Stale version directories — 9 dirs / 1,288 objects / 203,784,968 B
Artifact: `stale_dirs_approval_2026-08-29.json` · fingerprint
`9f8c654b0c3a45600ef6789ae61e3b7902ba02bf6a153b5a8d471b4a7b8c03b3`
```bash
cd /Users/seancheick/Downloads/dsld_clean && source scripts/python_env.sh && "$PG_PYTHON" -c "import sys; sys.path.insert(0,'scripts'); import env_loader; from release_safety.delete_stale_version_dirs import _main; sys.exit(_main(['--execute','--approval-report','reports/storage_cleanup/stale_dirs_approval_2026-08-29.json','--expected-count','1288','--expected-bytes','203784968','--fingerprint','9f8c654b0c3a45600ef6789ae61e3b7902ba02bf6a153b5a8d471b4a7b8c03b3']))"
```
Candidates: 2026.06.08.231328 · 06.15.180403 · 06.16.192123 · 08.08.120622 ·
08.13.204005 · 08.19.035832 · 08.19.201500 · 08.24.165613 · 08.25.090053.
Fresh-set fingerprint proof + manifest recheck under one lock hold; per-dir
absence proofs afterward.

### (A) July quarantine hard-delete — LAST; IRREVERSIBLE
Artifact: `sweep_approval_v2_2026-08-29.json` (identity-bound: every object's
path+size+eTag) · **18,391 objects / 2,375,048,433 B** · fingerprint
`1b493e268a153a639f98640733c70618cdba6d0988e1a82b539d5813589bbfa6`
```bash
cd /Users/seancheick/Downloads/dsld_clean && source scripts/python_env.sh && "$PG_PYTHON" scripts/sweep_quarantine.py --execute --approval-report reports/storage_cleanup/sweep_approval_v2_2026-08-29.json --expected-count 18391 --expected-bytes 2375048433 --fingerprint 1b493e268a153a639f98640733c70618cdba6d0988e1a82b539d5813589bbfa6 --flutter-repo "/Users/seancheick/PharmaGuide ai" --dist-dir scripts/dist --result-out reports/storage_cleanup/sweep_result_2026-08-29.json
```
Aug-06/Aug-28 batches structurally untouchable before their dates; any
same-path content drift, set drift, TTL mismatch, or protected-only-copy
condition refuses the whole run; deletion is proven by re-listing.

## Recovery / rollback boundaries

- (C): reversible — DROP FUNCTIONs; no data touched.
- (B): deletes dead artifacts referenced by no manifest row, registry row, or
  index; not recoverable, but nothing references them.
- (A): the point of no return for July's 2.21 GiB — 13 days past its window.
- Aug-28's 20.43 GiB stays recoverable until Sep 28; the storage bill falls
  materially only after that sweep (Sep 6: 963 obj; Sep 28: 118,947 obj).

## Test evidence (this pass)

- Sweep CLI: 20 tests · stale-dir suite: 102 · determinism (behavioral,
  4 hash seeds, mutation-checked): 1 · full storage slice green.
- `scripts/test.sh fast` and `scripts/test.sh release`: recorded in the final
  report alongside this package. Both repos clean and pushed.
