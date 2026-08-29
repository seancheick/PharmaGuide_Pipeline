# Storage-inventory RPC — exact-version rollout runbook (2026-08-29)

**Canonical migration owner:** `/Users/seancheick/PharmaGuide ai/supabase/migrations/20260830090000_storage_inventory_rpc.sql`

**SHA-256:** `df3eedb4d840a95df90873dd91185bce3239e83a97b802adb2da8a42b5534062`

**Version:** `20260830090000` (ahead of live head `20260829151221` before rollout)

## Ownership and history

The linked Flutter repository is the single executable Supabase migration
owner for this RPC. The pipeline repository consumes the functions but carries
no duplicate migration SQL.

This production project has legitimate older migrations owned by more than one
repository, so a blanket `supabase db push` refuses before reaching the new
file. Do not rewrite those historical rows. The pinned rollout script applies
only the reviewed SQL and then records exactly `20260830090000` through
Supabase's supported migration-repair command:

```bash
cd "/Users/seancheick/PharmaGuide ai"
tool/apply_storage_inventory_rpc.sh --execute
```

The script refuses a changed file hash. It also refuses completion unless all
three functions exist, anon/authenticated cannot execute them, service_role can,
the allowed-prefix policy behaves correctly, and a live summary succeeds. It
never edits `supabase_migrations.schema_migrations` directly.

## Query-plan proof

The reviewed predicate was measured live with `EXPLAIN (ANALYZE, BUFFERS)`:

    Index Scan using idx_objects_bucket_id_name on objects o
      Index Cond: ((bucket_id = 'pharmaguide')
                   AND (name >= 'shared/details/sha256/' COLLATE "C")
                   AND (name < 'shared/details/sha2560' COLLATE "C"))
      rows=16528, Execution Time: 3788 ms (cold: shared read=4357)

This is a bounded index range scan, not a sequential scan. The page function
uses the same range plus `ORDER BY name COLLATE "C" LIMIT <= 1000`.

## Post-apply gates

All must pass before treating the RPC path as verified:

1. Remote migration history contains exactly `20260830090000`.
2. The rollout script's database-side live-contract assertion passes.
3. A forbidden prefix raises SQLSTATE `22023`.
4. Three full walker-vs-RPC inventories match on names, sizes, eTags, counts,
   bytes, and digest.
5. An injected RPC failure falls back to the 256-shard walker.
6. Supabase security and performance advisors show no new actionable finding.

The shard walker remains the permanent fallback. Any RPC error, malformed or
short-invalid page, cursor violation, or summary mismatch fails the fast path
and uses the walker.
