# Storage Maintenance — Final Execution Package v3 (2026-08-29)

Supersedes v2. This revision closes the remaining audit gaps before production
execution. The order remains: **RPC → stale version directories → July sweep**.
The irreversible sweep is last.

## Corrections since v2

1. **One migration owner.** The storage-inventory RPC now exists only at
   `/Users/seancheick/PharmaGuide ai/supabase/migrations/20260830090000_storage_inventory_rpc.sql`.
   The linked Flutter repository owns deployment; the pipeline owns only its
   client and parity gates. Reviewed SHA-256:
   `df3eedb4d840a95df90873dd91185bce3239e83a97b802adb2da8a42b5534062`.
2. **No blanket history rewrite.** The production project has legitimate
   older multi-owner migration history. The pinned rollout applies only the
   exact reviewed SQL, records only version `20260830090000` with Supabase's
   supported repair command, and asserts the live function/permission/prefix
   contract inside PostgreSQL.
3. **Manifest identity is load-bearing.** Stale-directory execution now
   compares the approved retained-manifest digest with a fresh digest under the
   same release-lock hold as set revalidation and deletion. A changed manifest
   refuses even when candidate count, bytes, and fingerprint happen to match.
4. **Churn is reproducible.** `scripts/analyze_blob_churn.py` downloaded and
   SHA-256-verified every old/new pair. The committed report and full pair
   ledger bind index digests, product IDs, old/new blob hashes, sizes,
   classification, and changed field paths.

## Reproduced churn result

- Versions: `2026.08.26.141540` → `2026.08.27.162958`
- Index entries: 15,336 → 15,336; added/removed products: 0/0
- Changed common-product pairs: **1,192**, errors: **0**
- Pair fingerprint:
  `1e4814b881b9d2706296050e1220d7fead9cf871f5001b130e12ebbb0726bcf9`
- Sources-order-only: **1,044 / 453,761,407 new bytes**
- Other-order-only: **0**; serialization-only: **0**
- Semantic: **148 / 86,402,112 new bytes**

Artifacts:

- `churn_diagnosis_reproducible_2026-08-29.json`
- `churn_pair_ledger_2026-08-29.json`

The blend-source ordering fix is already in the producer and is pinned across
multiple `PYTHONHASHSEED` values. The expected reduction is still a projection
until the next ordinary catalog rebuild measures it.

## Production gates

### C — storage-inventory RPC (reversible)

Run the canonical Flutter rollout script. It verifies the exact file hash,
applies only the reviewed SQL, aligns only version `20260830090000`, and asserts
the live database contract. Then require three full walker/RPC parity passes,
an injected-failure fallback pass, and clean Supabase advisors. See
`rpc_rollout_prep_2026-08-29.md`.

### B — stale version directories

Regenerate the dry approval artifact immediately before execution. Under the
release lock, require exact equality of retained-manifest digest, candidate
fingerprint, count, and bytes. Delete only directories with no manifest row,
then prove every candidate directory absent and every retained directory
present.

The prior reviewed baseline was 9 directories / 1,288 objects /
203,784,968 bytes, fingerprint
`9f8c654b0c3a45600ef6789ae61e3b7902ba02bf6a153b5a8d471b4a7b8c03b3`.
Fresh production state is authoritative.

### A — July quarantine sweep (irreversible; last)

Regenerate the eligibility artifact immediately before execution. Require the
full path/size/eTag identity, TTL 30 days, protected-set proof, exact flags, and
post-delete absence inventory. August quarantine roots remain out of scope.

The prior reviewed baseline was 18,391 objects / 2,375,048,433 bytes,
fingerprint
`1b493e268a153a639f98640733c70618cdba6d0988e1a82b539d5813589bbfa6`.
Fresh production state is authoritative.

## Stop conditions

Any changed file hash, manifest digest, candidate set, count, byte total, eTag,
permission, prefix behavior, inventory parity, protected set, or postcondition
stops the sequence. Nothing is forced through a mismatch.
