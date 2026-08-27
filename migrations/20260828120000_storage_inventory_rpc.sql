-- Storage-inventory RPCs (Phase 4 of the storage-cleanup acceleration plan).
--
-- STATUS: AUTHORED, NOT APPLIED. Applying this to production requires its own
-- explicit approval (gate (c) in the approved plan). Apply via the MCP
-- apply_migration tool, then repair the schema_migrations stamp (MCP stamps
-- apply-time versions, not file prefixes — see
-- feedback_mcp_apply_migration_version_stamps).
--
-- Purpose: replace the 256-request, ~5-minute shard walk with two read-only
-- functions. The client (release_safety.blob_inventory.inventory_detail_blobs
-- _via_rpc) validates every row, requires strictly-monotonic keyset cursors,
-- and cross-checks the page stream against the summary; ANY disagreement
-- falls back to the shard walker, which remains the permanent authority.
--
-- Security model (verified against the live project before authoring):
--   * SECURITY INVOKER — service_role already holds direct SELECT on
--     storage.objects; no privilege escalation is involved.
--   * EXECUTE revoked from PUBLIC/anon/authenticated; granted only to
--     service_role. Verify post-apply that anon/authenticated calls fail.
--   * Prefix arguments are restricted to the recognized PharmaGuide layouts
--     (active blob store and dated quarantine trees) — the functions refuse
--     arbitrary bucket spelunking even for a privileged caller.
--
-- Index expectations (verified present):
--   * idx_objects_bucket_id_name  btree (bucket_id, name COLLATE "C")
--   * name_prefix_search          btree (name text_pattern_ops)
-- The predicates below compare name COLLATE "C" as a half-open range
-- [prefix||'/', prefix||'0') — '0' is the successor of '/' in ASCII — which
-- the "C"-collated index serves as a range scan. Rollout gate: EXPLAIN
-- (ANALYZE, BUFFERS) on both functions' queries must show a bounded index or
-- bitmap range scan; a whole-table seq scan blocks rollout.

create or replace function public.pg_storage_inventory_prefix_ok(p_prefix text)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select p_prefix = 'shared/details/sha256'
      or p_prefix ~ '^shared/details/sha256/[0-9a-f]{2}$'
      or p_prefix ~ '^shared/quarantine/\d{4}-\d{2}-\d{2}$'
      or p_prefix ~ '^shared/quarantine/\d{4}-\d{2}-\d{2}/[0-9a-f]{2}$'
$$;

comment on function public.pg_storage_inventory_prefix_ok(text) is
  'Recognized PharmaGuide storage prefixes for the inventory RPCs. '
  'Anything else is refused regardless of caller privileges.';

create or replace function public.pg_storage_inventory_summary(p_prefix text)
returns table (object_count bigint, total_bytes bigint)
language plpgsql
stable
security invoker
set search_path = ''
as $$
begin
  if not public.pg_storage_inventory_prefix_ok(p_prefix) then
    raise exception 'unrecognized inventory prefix: %', p_prefix
      using errcode = '22023';
  end if;
  return query
    select count(*)::bigint,
           coalesce(sum((o.metadata ->> 'size')::bigint), 0)::bigint
    from storage.objects o
    where o.bucket_id = 'pharmaguide'
      and o.name collate "C" >= (p_prefix || '/') collate "C"
      and o.name collate "C" <  (p_prefix || '0') collate "C";
end;
$$;

create or replace function public.pg_storage_inventory_page(
  p_prefix text,
  p_after  text default null,
  p_limit  integer default 1000
)
returns table (name text, size bigint, etag text, updated_at timestamptz)
language plpgsql
stable
security invoker
set search_path = ''
as $$
begin
  if not public.pg_storage_inventory_prefix_ok(p_prefix) then
    raise exception 'unrecognized inventory prefix: %', p_prefix
      using errcode = '22023';
  end if;
  return query
    select o.name,
           coalesce((o.metadata ->> 'size')::bigint, 0),
           o.metadata ->> 'eTag',
           o.updated_at
    from storage.objects o
    where o.bucket_id = 'pharmaguide'
      and o.name collate "C" >= (p_prefix || '/') collate "C"
      and o.name collate "C" <  (p_prefix || '0') collate "C"
      and (p_after is null or o.name collate "C" > p_after collate "C")
    order by o.name collate "C"
    limit least(greatest(coalesce(p_limit, 1000), 1), 1000);
end;
$$;

comment on function public.pg_storage_inventory_summary(text) is
  'Read-only inventory summary for one recognized PharmaGuide prefix. '
  'Cross-checked by the client against the page stream; mismatch = fallback.';
comment on function public.pg_storage_inventory_page(text, text, integer) is
  'Keyset page (<=1000 rows, ORDER BY name COLLATE "C") of one recognized '
  'prefix. A page shorter than the limit is normal termination.';

-- Least privilege: only the pipeline (service_role) may call these.
revoke execute on function public.pg_storage_inventory_prefix_ok(text)
  from public, anon, authenticated;
revoke execute on function public.pg_storage_inventory_summary(text)
  from public, anon, authenticated;
revoke execute on function public.pg_storage_inventory_page(text, text, integer)
  from public, anon, authenticated;
grant execute on function public.pg_storage_inventory_prefix_ok(text)
  to service_role;
grant execute on function public.pg_storage_inventory_summary(text)
  to service_role;
grant execute on function public.pg_storage_inventory_page(text, text, integer)
  to service_role;
