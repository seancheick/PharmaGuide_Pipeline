# Storage-inventory RPC — rollout prep (gate C) — REVISED 2026-08-29

**Migration file:** `migrations/20260830090000_storage_inventory_rpc.sql`
**SHA-256:** `74ba616ca6144af9ca05c51c8ddc62f5190259b8e29879da1eed5af40baa794a`
**Status:** authored, NOT applied. Nothing below runs without explicit approval.

## Ownership model (revised — no history surgery)

This repo's `migrations/` directory is the canonical owner of pipeline schema
changes. The file was RE-VERSIONED forward of the live history head
(`20260829151221`) to `20260830090000`, so applying it needs **no
migration-history editing**: apply under this exact version and the listing
stays aligned by construction. If the applying tool stamps a different
version anyway, use the SUPPORTED repair —
`supabase migration repair --status applied 20260830090000` (and
`--status reverted <wrong-version>`) — never direct
`supabase_migrations.schema_migrations` table edits. Deployment is blocked
until the migration listing shows exactly `20260830090000`.

## Query-plan proof (run live 2026-08-29, read-only)

`EXPLAIN (ANALYZE, BUFFERS)` on the summary function's exact predicate:

    Index Scan using idx_objects_bucket_id_name on objects o
      Index Cond: ((bucket_id = 'pharmaguide') AND (name >= 'shared/details/sha256/' COLLATE "C")
                   AND (name < 'shared/details/sha2560' COLLATE "C"))
      rows=16528, Execution Time: 3788 ms (cold: shared read=4357)

Bounded index range scan — the "no seq scan" gate passes. The page function
uses the same predicate + `ORDER BY name COLLATE "C" LIMIT <=1000`.

## Post-apply verification (all must pass before enabling the flag)

1. Migration listing shows `20260830090000` (blockers above otherwise).
2. Permissions:
```sql
SELECT r.rolname,
       has_function_privilege(r.rolname, 'public.pg_storage_inventory_summary(text)', 'EXECUTE') AS can_summary,
       has_function_privilege(r.rolname, 'public.pg_storage_inventory_page(text,text,integer)', 'EXECUTE') AS can_page
FROM (VALUES ('anon'), ('authenticated'), ('service_role')) AS r(rolname);
-- REQUIRED: anon=false/false, authenticated=false/false, service_role=true/true
```
3. Unrecognized prefix refused: `SELECT * FROM public.pg_storage_inventory_summary('shared/../../etc');` must raise.
4. Three locked walker-vs-RPC parity scans:
   `scripts/reconcile_orphan_blobs.py … --verify-inventory` x3 -> PARITY OK
   (names, sizes, eTags, counts, bytes — full-set, never sampled).
5. Fallback proof live once (wrong fn name under the flag -> walker used).
6. Supabase security + performance advisors; walker stays the permanent
   authority; `PG_STORAGE_INVENTORY_RPC` stays default-off.
