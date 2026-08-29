# Storage-inventory RPC — rollout prep (gate: approval (c))

**Migration file:** `migrations/20260828120000_storage_inventory_rpc.sql`
**SHA-256:** `43fabd7825ced3c781d851ec223ac435557fd482b510895a9f3b427f8901f87c`
**Status:** authored, NOT applied. Nothing below runs without explicit approval.

## Query-plan proof (run live 2026-08-29, read-only)

`EXPLAIN (ANALYZE, BUFFERS)` on the summary function's exact predicate:

    Index Scan using idx_objects_bucket_id_name on objects o
      Index Cond: ((bucket_id = 'pharmaguide') AND (name >= 'shared/details/sha256/' COLLATE "C")
                   AND (name < 'shared/details/sha2560' COLLATE "C"))
      rows=16528, Execution Time: 3788 ms (cold: shared read=4357)

Bounded index range scan — the rollout gate ("no seq scan") passes. The page
function uses the same predicate + `ORDER BY name COLLATE "C" LIMIT ≤1000`.

## Migration-history repair (required, per MCP stamping behavior)

Live head is `20260829151221`; our file is `20260828120000` (behind head).
`apply_migration` stamps an APPLY-TIME version, so without repair a later
`db push` would replay the file. Table columns confirmed:
(version text, statements ARRAY, name text, created_by text,
idempotency_key text, rollback ARRAY).

Immediately after the approved `apply_migration`:

```sql
DELETE FROM supabase_migrations.schema_migrations
 WHERE name = 'storage_inventory_rpc' AND version <> '20260828120000';
INSERT INTO supabase_migrations.schema_migrations (version, name)
VALUES ('20260828120000', 'storage_inventory_rpc')
ON CONFLICT (version) DO NOTHING;
```

## Post-apply verification (all must pass before enabling the flag)

1. Permissions:
```sql
SELECT r.rolname,
       has_function_privilege(r.rolname, 'public.pg_storage_inventory_summary(text)', 'EXECUTE') AS can_summary,
       has_function_privilege(r.rolname, 'public.pg_storage_inventory_page(text,text,integer)', 'EXECUTE') AS can_page
FROM (VALUES ('anon'), ('authenticated'), ('service_role')) AS r(rolname);
-- REQUIRED: anon=false/false, authenticated=false/false, service_role=true/true
```
2. Unrecognized prefix refused: `SELECT * FROM public.pg_storage_inventory_summary('shared/../../etc');` must raise.
3. Three locked walker-vs-RPC parity scans:
   `scripts/reconcile_orphan_blobs.py … --verify-inventory` ×3 → PARITY OK each time
   (names, sizes, eTags, counts, bytes — full-set, not sampled).
4. Fallback proof: with `PG_STORAGE_INVENTORY_RPC=1` and a fault injected
   (revoke, bad row), `inventory_detail_blobs` must fall back to the walker
   (pinned by test_blob_inventory_rpc; re-verify live once with a wrong fn name).
5. Run Supabase security + performance advisors; walker stays the permanent
   authority; the env flag defaults OFF.
