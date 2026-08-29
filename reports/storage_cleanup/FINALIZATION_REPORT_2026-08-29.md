# Storage-maintenance finalization — 2026-08-29

## Outcome

The storage-maintenance acceleration and safety work is complete. The fast
inventory RPC is live, stale version directories are gone, the remaining
TTL-eligible July quarantine was hard-deleted from an exact path/size/eTag
approval artifact, and the final active-blob reconciliation reports zero
orphans.

## Code and deployment

- Pipeline `main`: `90c1a2668c5e20eca29a05bb7b31a137e44632b7`
  - stale cleanup binds execution to the retained-manifest snapshot;
  - churn analysis is complete-population and reproducible;
  - the duplicate RPC migration was removed from this repository.
- Flutter/app `main`: `385bfc8a3804c3359f49a04f9833c012d232571f`
  - canonical migration owner:
    `supabase/migrations/20260830090000_storage_inventory_rpc.sql`;
  - migration SHA-256:
    `df3eedb4d840a95df90873dd91185bce3239e83a97b802adb2da8a42b5534062`.
- Production Supabase project: `omayamxacvacrnvdvzhr`.
- Migration `20260830090000_storage_inventory_rpc` is applied and recorded.
- Three full locked walker/RPC parity passes matched exactly: 16,528 blobs,
  3,558,214,275 bytes, identical names, sizes, and eTags.
- The production fallback drill passed: an injected RPC failure fell back to
  the shard walker and returned the identical shard-00 inventory.

## Verification before production maintenance

- Pipeline focused storage tests: 99 passed.
- Pipeline fast suite: 12,308 passed, 140 skipped, 0 failed.
- Pipeline release gate: 123/123 passed, including source-of-truth,
  form-evidence, functional-role, RxCUI, PubMed, and clinical-evidence gates.
- Flutter `make check`: analysis clean and 3,376 tests passed.
- Reproducible full-population churn replay: 1,192 pairs, 1,044
  source-order-only, 148 semantic, 0 errors. Avoidable new bytes were
  453,761,407; semantic new bytes were 86,402,112.

## Stale version-directory cleanup

Approval artifact:
`reports/storage_cleanup/stale_dirs_approval_final_2026-08-29.json`

- Approved and deleted: 9 directories, 1,288 objects, 203,784,968 bytes.
- Approval fingerprint:
  `9f8c654b0c3a45600ef6789ae61e3b7902ba02bf6a153b5a8d471b4a7b8c03b3`.
- Failures: 0.
- Independent post-delete plan: 0 stale directories, 0 objects, 0 bytes.
- Retained manifest versions remained present:
  `2026.08.26.141540` and `2026.08.27.162958`.
- Audit receipt:
  `reports/release_audit/20260829T231702Z_be608e17fce7.jsonl`.

## July quarantine hard-delete

Approval artifact:
`reports/storage_cleanup/sweep_approval_final_2026-08-29.json`

- TTL: 30 days with the strict 31st-day eligibility boundary.
- Approved date: `2026-07-17` only.
- Approved and proven absent: 18,391 objects, 2,375,048,433 bytes.
- Approval fingerprint:
  `1b493e268a153a639f98640733c70618cdba6d0988e1a82b539d5813589bbfa6`.
- eTag coverage at approval: 18,391 / 18,391.
- Residuals: 0. Failures: 0. Resume checkpoint self-cleared.
- Result receipt:
  `reports/storage_cleanup/sweep_result_final_2026-08-29.json`.
- Independent post-delete inventory: 0 objects and 0 bytes under
  `shared/quarantine/2026-07-17`.

The July objects were permanently deleted and cannot be recovered. This was
the reviewed TTL-expired set; no August recovery-window object was included.

## Recovery-window preservation

Fresh complete RPC inventories after the July sweep matched the frozen
baselines exactly:

| Quarantine date | Objects | Bytes | eTag coverage | Earliest sweep eligibility |
| --- | ---: | ---: | ---: | --- |
| `2026-08-06` | 963 | 229,699,017 | 963 / 963 | 2026-09-06 |
| `2026-08-28` | 118,947 | 21,933,347,321 | 118,947 / 118,947 | 2026-09-28 |

Future sweeps remain separate approval-gated maintenance actions; they do not
run as an unattended catalog-release side effect.

## Final active-storage proof

Report:
`reports/storage_cleanup/final_orphan_verification_2026-08-29.json`

- Active objects examined: 16,528.
- Unique detail blobs: 16,528.
- Active bytes: 3,558,214,275.
- Protected union: 16,528.
- Orphans: 0; reclaimable bytes: 0.
- Listing failures: 0; retries: 0; integrity failures: 0.
- Candidate digest: empty-set SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Protected digest:
  `96fc0f600c5c730c668d2d11bc8670ca26d5f5102840a39968683f6545bfdcab`.

## Separate non-blocking backlog

Supabase advisors reported no new finding caused by the storage-inventory
RPC. Existing notices remain for service-only RLS tables, authenticated
`SECURITY DEFINER` submission/usage functions, missing foreign-key indexes,
unused indexes, and the Auth connection strategy. Those are separate schema
and performance-review items and were not changed during this storage-only
work.
