-- PharmaGuide Supabase Schema
-- Run this in the Supabase SQL Editor to set up the project.
-- Version: 2.1.0
-- Date: 2026-07-10
-- Reviewed by: Flutter expert + PostgreSQL expert

-- =============================================================================
-- 1. Pipeline Distribution Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS export_manifest (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  db_version       text NOT NULL,
  pipeline_version text NOT NULL,
  scoring_version  text NOT NULL,
  schema_version   text NOT NULL,
  product_count    integer NOT NULL,
  checksum         text NOT NULL,
  min_app_version  text NOT NULL DEFAULT '1.0.0',
  generated_at     timestamptz NOT NULL,
  created_at       timestamptz DEFAULT now(),
  is_current       boolean DEFAULT true
);

-- =============================================================================
-- 2. User Tables (App-facing)
-- =============================================================================

-- Flutter creates local entry ids, but remote state is identified by
-- `(user_id, dsld_id)`: one current state per catalog product. This must be a
-- full UNIQUE constraint so PostgREST can select it as the upsert target; the
-- retired partial active-only index caused 23505 replacement-row failures.
-- `id` remains text, not uuid, because the client sends its entry id verbatim.
-- `type` is hard-pinned to 'supplement' (column CHECK + RLS WITH CHECK) so
-- medication PHI can never reach the cloud. The reconciliation block below
-- heals pre-existing deployments on re-run and asserts this contract.
CREATE TABLE IF NOT EXISTS user_stacks (
  id                text PRIMARY KEY,                                  -- client-generated "<dsldId>_<microseconds>"; NOT uuid
  user_id           uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  type              text NOT NULL DEFAULT 'supplement'                 -- PHI guard: medications never sync here
                    CHECK (type = 'supplement'),
  name              text,
  dsld_id           text NOT NULL,                                    -- every synced row is a catalog supplement
  ingredient_keys   text,                                             -- JSON-encoded canonical ingredient ids
  dosage            text,
  frequency         text,
  supply_count      integer,
  source_device_id  text,
  client_updated_at timestamptz NOT NULL,                              -- LWW ordering value supplied by Flutter
  deleted_at        timestamptz,
  added_at          timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now(),
  CONSTRAINT user_stacks_user_id_id_unique UNIQUE (user_id, id),       -- cross-user id-collision guard
  CONSTRAINT user_stacks_user_dsld_unique UNIQUE (user_id, dsld_id)    -- canonical remote product-state key
);

-- Reconcile pre-existing deployments to the contract above (idempotent).
-- CREATE TABLE IF NOT EXISTS is a no-op on an existing table, so these ALTERs
-- are how a live DB that predates the corrected definition gets healed when
-- supabase_schema.sql is re-run. Safe to run repeatedly.
DO $$
BEGIN
  -- id uuid -> text (lossless widening; the 2026-06 sync-crash fix)
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='user_stacks'
               AND column_name='id' AND data_type='uuid') THEN
    ALTER TABLE public.user_stacks ALTER COLUMN id TYPE text USING id::text;
  END IF;

  -- legacy 'timing' -> 'frequency' (matches the Flutter column name)
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='user_stacks' AND column_name='timing')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='user_stacks' AND column_name='frequency') THEN
    ALTER TABLE public.user_stacks RENAME COLUMN timing TO frequency;
  END IF;

  -- columns the Flutter client sends
  ALTER TABLE public.user_stacks ADD COLUMN IF NOT EXISTS type text;
  ALTER TABLE public.user_stacks ADD COLUMN IF NOT EXISTS name text;
  ALTER TABLE public.user_stacks ADD COLUMN IF NOT EXISTS ingredient_keys text;

  -- A synced row is always a catalog supplement. Fail closed rather than
  -- inventing an identity or deleting an unexpected legacy row.
  IF EXISTS (
    SELECT 1 FROM public.user_stacks WHERE dsld_id IS NULL
  ) THEN
    RAISE EXCEPTION
      'user_stacks contains rows without dsld_id; remediate before enforcing the product-state contract';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.user_stacks WHERE client_updated_at IS NULL
  ) THEN
    RAISE EXCEPTION
      'user_stacks contains rows without client_updated_at; remediate before enforcing LWW';
  END IF;

  -- Keep one newest state per product before adding the full UNIQUE key. A
  -- tombstone is the product's current state, not retained history.
  DELETE FROM public.user_stacks AS stack
  USING (
    SELECT
      ctid,
      row_number() OVER (
        PARTITION BY user_id, dsld_id
        ORDER BY client_updated_at DESC, updated_at DESC, id DESC
      ) AS row_number
    FROM public.user_stacks
  ) AS ranked
  WHERE stack.ctid = ranked.ctid
    AND ranked.row_number > 1;

  ALTER TABLE public.user_stacks ALTER COLUMN dsld_id SET NOT NULL;
  ALTER TABLE public.user_stacks ALTER COLUMN client_updated_at SET NOT NULL;

  -- type backstop: default + not null + supplement-only CHECK
  UPDATE public.user_stacks SET type='supplement' WHERE type IS NULL;
  ALTER TABLE public.user_stacks ALTER COLUMN type SET DEFAULT 'supplement';
  ALTER TABLE public.user_stacks ALTER COLUMN type SET NOT NULL;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid='public.user_stacks'::regclass
                   AND conname='user_stacks_type_supplement_check') THEN
    ALTER TABLE public.user_stacks
      ADD CONSTRAINT user_stacks_type_supplement_check CHECK (type='supplement');
  END IF;

  -- cross-user id-collision guard
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid='public.user_stacks'::regclass
                   AND conname='user_stacks_user_id_id_unique') THEN
    ALTER TABLE public.user_stacks
      ADD CONSTRAINT user_stacks_user_id_id_unique UNIQUE (user_id, id);
  END IF;

  -- Canonical upsert target used by Flutter. Add this before removing the
  -- historical partial index so no duplicate-active window exists.
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid='public.user_stacks'::regclass
                   AND conname='user_stacks_user_dsld_unique') THEN
    ALTER TABLE public.user_stacks
      ADD CONSTRAINT user_stacks_user_dsld_unique UNIQUE (user_id, dsld_id);
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS user_usage (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid REFERENCES auth.users NOT NULL,
    scans_today       integer DEFAULT 0 CHECK (scans_today >= 0),
    ai_messages_today integer DEFAULT 0 CHECK (ai_messages_today >= 0),
    reset_day_utc     date DEFAULT ((now() AT TIME ZONE 'UTC')::date)
);

CREATE TABLE IF NOT EXISTS pending_products (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid REFERENCES auth.users NOT NULL,
  upc            text NOT NULL,
  normalized_upc text,
  product_name   text,
  brand          text,
  image_url      text,
  submitter_note text,
  status         text DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'approved', 'rejected', 'duplicate')),
  review_notes   text,
  reviewed_at    timestamptz,
  reviewed_by    text,
  submitted_at   timestamptz DEFAULT now()
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_user_stacks_user ON user_stacks(user_id);
-- Retired: a partial index cannot be targeted by the client's PostgREST
-- upsert and would reintroduce the replacement-row 23505 bug.
DROP INDEX IF EXISTS public.idx_user_stacks_user_dsld_active;
CREATE INDEX IF NOT EXISTS idx_user_usage_user ON user_usage(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_usage_daily ON user_usage(user_id, reset_day_utc);
CREATE INDEX IF NOT EXISTS idx_pending_products_user ON pending_products(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_products_status ON pending_products(status) WHERE status = 'pending';
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_products_user_normalized_upc_pending
  ON pending_products(user_id, normalized_upc)
  WHERE status = 'pending' AND normalized_upc IS NOT NULL;

-- Partial unique index: enforces exactly one is_current=true row at any time.
-- Prevents split-brain if rotate_manifest is called concurrently.
CREATE UNIQUE INDEX IF NOT EXISTS idx_export_manifest_one_current
  ON export_manifest((true))
  WHERE is_current = true;

-- =============================================================================
-- 4. Triggers
-- =============================================================================

-- Auto-update updated_at on user_stacks edits
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
-- Fixed search_path prevents search_path-injection (advisor 0011). public is
-- listed so the body's unqualified table refs resolve; pg_catalog for now() etc.
$$ LANGUAGE plpgsql SET search_path = public, pg_catalog;

DROP TRIGGER IF EXISTS user_stacks_updated_at ON user_stacks;
CREATE TRIGGER user_stacks_updated_at
  BEFORE UPDATE ON user_stacks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Client timestamp LWW must be enforced in the database, not inferred from
-- request arrival order. `zz_` runs after user_stacks_updated_at and restores
-- OLD for a stale write, including the server-side updated_at value.
CREATE OR REPLACE FUNCTION public.keep_newest_user_stack_state()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF NEW.client_updated_at < OLD.client_updated_at
     OR (
       NEW.client_updated_at = OLD.client_updated_at
       AND NEW.id < OLD.id
     ) THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS zz_user_stacks_keep_newest_state ON user_stacks;
CREATE TRIGGER zz_user_stacks_keep_newest_state
  BEFORE UPDATE ON user_stacks
  FOR EACH ROW EXECUTE FUNCTION public.keep_newest_user_stack_state();

-- Bootstrap postcondition: this script is intentionally re-runnable, so it
-- must fail loudly if a future edit leaves the app-facing state contract in a
-- shape Flutter cannot safely upsert or order.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.user_stacks'::regclass
      AND conname = 'user_stacks_user_dsld_unique'
  )
  OR NOT (
    SELECT attnotnull
    FROM pg_attribute
    WHERE attrelid = 'public.user_stacks'::regclass
      AND attname = 'dsld_id'
  )
  OR NOT (
    SELECT attnotnull
    FROM pg_attribute
    WHERE attrelid = 'public.user_stacks'::regclass
      AND attname = 'client_updated_at'
  )
  OR EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = 'user_stacks'
      AND indexname = 'idx_user_stacks_user_dsld_active'
  )
  OR NOT EXISTS (
    SELECT 1
    FROM pg_trigger
    WHERE tgrelid = 'public.user_stacks'::regclass
      AND tgname = 'zz_user_stacks_keep_newest_state'
      AND NOT tgisinternal
  ) THEN
    RAISE EXCEPTION 'user_stacks product-state contract drift';
  END IF;
END$$;

-- =============================================================================
-- 5. Row Level Security
-- =============================================================================

-- export_manifest: anyone can read, only service role can write
ALTER TABLE export_manifest ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read manifest" ON export_manifest
  FOR SELECT USING (true);

-- user_stacks: users own their rows. INSERT/UPDATE additionally enforce
-- type='supplement' (WITH CHECK) — the DB-level half of the belt-and-suspenders
-- that keeps medication PHI out of the cloud (the client filters too). Granular
-- per-command policies REPLACE the old catch-all "Users manage own stacks"
-- FOR ALL policy, which had no WITH CHECK and so let a client write a
-- type='medication' row for its own user_id. DROP IF EXISTS heals existing
-- deployments on re-run. (SELECT auth.uid()) is kept for per-statement caching.
ALTER TABLE user_stacks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users manage own stacks"          ON user_stacks;
DROP POLICY IF EXISTS "users_can_read_own_stack"         ON user_stacks;
DROP POLICY IF EXISTS "users_can_insert_own_supplements" ON user_stacks;
DROP POLICY IF EXISTS "users_can_update_own_supplements" ON user_stacks;
DROP POLICY IF EXISTS "users_can_delete_own_stack"       ON user_stacks;
CREATE POLICY "users_can_read_own_stack" ON user_stacks
  FOR SELECT USING ((SELECT auth.uid()) = user_id);
CREATE POLICY "users_can_insert_own_supplements" ON user_stacks
  FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id AND type = 'supplement');
CREATE POLICY "users_can_update_own_supplements" ON user_stacks
  FOR UPDATE USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id AND type = 'supplement');
CREATE POLICY "users_can_delete_own_stack" ON user_stacks
  FOR DELETE USING ((SELECT auth.uid()) = user_id);

-- user_usage: users can read their counters, but writes go through increment_usage
ALTER TABLE user_usage ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own usage" ON user_usage
  FOR SELECT USING ((SELECT auth.uid()) = user_id);

-- pending_products: users can submit and read their requests; status is server-owned
ALTER TABLE pending_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own submissions" ON pending_products
  FOR SELECT USING ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users submit pending products" ON pending_products
  FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);

-- =============================================================================
-- 6. RPC Functions
-- =============================================================================

-- 6a. Atomic manifest rotation (service_role only)
-- UPDATE old rows first, then INSERT new — all within a single PL/pgSQL transaction.
CREATE OR REPLACE FUNCTION rotate_manifest(
  p_db_version text,
  p_pipeline_version text,
  p_scoring_version text,
  p_schema_version text,
  p_product_count integer,
  p_checksum text,
  p_generated_at timestamptz,
  p_min_app_version text DEFAULT '1.0.0'
) RETURNS uuid AS $$
DECLARE
  new_id uuid;
BEGIN
  -- Guard: only service_role can rotate the manifest
  IF current_setting('request.jwt.claims', true)::json->>'role' IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'rotate_manifest is restricted to service_role';
  END IF;

  IF p_product_count < 0 THEN
    RAISE EXCEPTION 'product_count cannot be negative: %', p_product_count;
  END IF;

  -- Mark current as not current first (unique index allows only one true)
  UPDATE export_manifest
  SET is_current = false
  WHERE is_current = true;

  -- Insert new row
  INSERT INTO export_manifest (
    db_version, pipeline_version, scoring_version, schema_version,
    product_count, checksum, min_app_version, generated_at, is_current
  ) VALUES (
    p_db_version, p_pipeline_version, p_scoring_version, p_schema_version,
    p_product_count, p_checksum, p_min_app_version, p_generated_at, true
  ) RETURNING id INTO new_id;

  RETURN new_id;
END;
-- SECURITY DEFINER + fixed search_path (advisor 0011): public so unqualified
-- export_manifest refs resolve; pg_catalog for built-ins. Prevents a caller
-- from shadowing objects via an attacker-controlled search_path.
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog;

-- Restrict rotate_manifest to service_role only
REVOKE EXECUTE ON FUNCTION rotate_manifest(text, text, text, text, integer, text, timestamptz, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION rotate_manifest(text, text, text, text, integer, text, timestamptz, text) FROM anon;
REVOKE EXECUTE ON FUNCTION rotate_manifest(text, text, text, text, integer, text, timestamptz, text) FROM authenticated;
GRANT EXECUTE ON FUNCTION rotate_manifest(text, text, text, text, integer, text, timestamptz, text) TO service_role;

-- 6b. Atomic usage increment with UTC day rollover and server-side enforcement
-- Flutter calls this once a scan/AI action is ready to be committed, before
-- rendering an over-limit experience to the user.
-- Daily freemium limits reset on UTC day boundaries. Surface that policy in the app.
CREATE OR REPLACE FUNCTION increment_usage(
  p_user_id uuid,
  p_type text  -- 'scan' or 'ai_message'
) RETURNS jsonb AS $$
DECLARE
  v_usage user_usage%ROWTYPE;
  v_scans integer := 0;
  v_ai integer := 0;
  v_exceeded boolean := false;
  v_scan_limit constant integer := 20;
  v_ai_limit constant integer := 5;
  v_reset_day_utc date := (now() AT TIME ZONE 'UTC')::date;
BEGIN
  -- Guard: caller must own the user_id
  IF p_user_id IS DISTINCT FROM auth.uid() THEN
    RAISE EXCEPTION 'Unauthorized: cannot increment usage for another user';
  END IF;

  -- Guard: validate type
  IF p_type NOT IN ('scan', 'ai_message') THEN
    RAISE EXCEPTION 'Invalid usage type: %. Must be ''scan'' or ''ai_message''.', p_type;
  END IF;

  -- Upsert with automatic day rollover
  INSERT INTO user_usage (user_id, scans_today, ai_messages_today, reset_day_utc)
  VALUES (
    p_user_id,
    0,
    0,
    v_reset_day_utc
  )
  ON CONFLICT (user_id, reset_day_utc)
  DO NOTHING;

  SELECT *
  INTO v_usage
  FROM user_usage
  WHERE user_id = p_user_id AND reset_day_utc = v_reset_day_utc
  FOR UPDATE;

  IF p_type = 'scan' AND v_usage.scans_today >= v_scan_limit THEN
    v_exceeded := true;
  ELSIF p_type = 'ai_message' AND v_usage.ai_messages_today >= v_ai_limit THEN
    v_exceeded := true;
  ELSE
    UPDATE user_usage
    SET
      scans_today = CASE WHEN p_type = 'scan' THEN scans_today + 1 ELSE scans_today END,
      ai_messages_today = CASE WHEN p_type = 'ai_message' THEN ai_messages_today + 1 ELSE ai_messages_today END
    WHERE id = v_usage.id
    RETURNING scans_today, ai_messages_today
    INTO v_scans, v_ai;
  END IF;

  IF v_exceeded THEN
    v_scans := v_usage.scans_today;
    v_ai := v_usage.ai_messages_today;
  END IF;

  RETURN jsonb_build_object(
    'scans_today', v_scans,
    'ai_messages_today', v_ai,
    'limit_exceeded', v_exceeded,
    'reset_day_utc', v_reset_day_utc
  );
END;
-- SECURITY DEFINER + fixed search_path (advisor 0011): public so unqualified
-- user_usage refs resolve; pg_catalog for built-ins. Prevents a caller from
-- shadowing objects via an attacker-controlled search_path.
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog;

-- Grant increment_usage to authenticated users only (not anon)
REVOKE EXECUTE ON FUNCTION increment_usage(uuid, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION increment_usage(uuid, text) FROM anon;
GRANT EXECUTE ON FUNCTION increment_usage(uuid, text) TO authenticated;

-- =============================================================================
-- 7. Storage Bucket
-- =============================================================================
-- Create via Supabase Dashboard or API:
--   Bucket name: pharmaguide
--   Public: true (read via anon key)
--   File size limit: choose a plan/limit that supports the real pharmaguide_core.db size.
--   The historical 50MB note is no longer a safe assumption for the full export.
--
-- Folder structure:
--   pharmaguide/v{version}/pharmaguide_core.db
--   pharmaguide/v{version}/detail_index.json
--   pharmaguide/shared/details/sha256/{blob_sha256[0:2]}/{blob_sha256}.json
--   pharmaguide/shared/release_indexes/{db_version}/detail_index.json   -- P3 archived index
--   pharmaguide/shared/quarantine/{date}/{shard}/{hash}.json            -- P2 soft-deleted blobs

-- =============================================================================
-- 8. Catalog Release Registry (ADR-0001 P3.1)
-- =============================================================================
-- Multi-version live registry. Replaces the P1.4 interim bundled∪dist
-- heuristic in the orphan-blob protected-set computation.
--
-- Design highlights:
--   - State machine: PENDING -> VALIDATING -> ACTIVE -> RETIRED
--     (any failure during VALIDATING falls back to PENDING; never partially-active)
--   - Multiple ACTIVE rows are normal: bundled-on-installed-app + dist for
--     next release + ota_stable for current rollout can co-exist.
--   - DB-layer CHECK constraints enforce state-machine invariants
--     (so app-layer bugs cannot leave the registry in an inconsistent state).
--   - Partial index on ACTIVE keeps the protected-set query (the hot path)
--     fast as RETIRED rows accumulate.
--   - Public read (so consumer-side tooling can introspect); service-role write.
--
-- Channels (initial set, per ADR sign-off):
--   - bundled     : shipped in app binary; installed on user devices
--   - ota_stable  : delivered via OTA to all installed apps
--   - dev         : pipeline test build / pre-release
--   ota_beta is intentionally NOT included; add via ALTER TYPE when a real
--   beta cohort exists.

-- ENUMs are wrapped in DO blocks so re-running supabase_schema.sql is idempotent
-- (unlike CREATE TABLE IF NOT EXISTS, plain CREATE TYPE has no IF NOT EXISTS).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'catalog_release_state') THEN
    CREATE TYPE catalog_release_state AS ENUM (
      'PENDING',     -- row exists; not yet visible to consumers; blobs NOT protected
      'VALIDATING',  -- activation in progress; blobs ARE protected (transient)
      'ACTIVE',      -- live; visible via channel routing; blobs protected
      'RETIRED'      -- explicitly retired; blobs no longer protected
    );
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'catalog_release_channel') THEN
    CREATE TYPE catalog_release_channel AS ENUM (
      'bundled',
      'ota_stable',
      'dev'
    );
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS catalog_releases (
  db_version              text PRIMARY KEY,                              -- e.g. "2026.05.12.203133"
  state                   catalog_release_state NOT NULL DEFAULT 'PENDING',
  release_channel         catalog_release_channel NOT NULL,
  released_at             timestamptz NOT NULL DEFAULT now(),
  activated_at            timestamptz,                                   -- set when state -> ACTIVE
  retired_at              timestamptz,                                   -- set when state -> RETIRED
  retired_reason          text,                                          -- mandatory when retired_at IS NOT NULL
  bundled_in_app_versions text[] NOT NULL DEFAULT ARRAY[]::text[],       -- e.g. '{1.0.0, 1.0.1}'
  flutter_repo_commit     text,                                          -- SHA of Flutter bundle commit on main (channel=bundled only)
  detail_index_url        text,                                          -- shared/release_indexes/{db_version}/detail_index.json
  notes                   text,

  -- ACTIVE / RETIRED rows MUST have activated_at set (proves they passed activation).
  -- PENDING / VALIDATING rows are pre-activation; activated_at is NULL.
  CONSTRAINT activated_at_set_iff_active_or_retired
    CHECK (state IN ('PENDING', 'VALIDATING') OR activated_at IS NOT NULL),

  -- RETIRED rows MUST have retired_at + retired_reason; non-RETIRED rows MUST have neither.
  -- Forces the operator to record WHY a release was retired (audit-grade evidence).
  CONSTRAINT retired_fields_consistent
    CHECK ((state = 'RETIRED' AND retired_at IS NOT NULL AND retired_reason IS NOT NULL)
        OR (state != 'RETIRED' AND retired_at IS NULL AND retired_reason IS NULL)),

  -- Bundled rows MUST record the Flutter commit that bundled them (provenance).
  -- ota_stable / dev channels can omit (no Flutter bundle commit per row).
  CONSTRAINT bundled_requires_flutter_commit
    CHECK (release_channel != 'bundled' OR flutter_repo_commit IS NOT NULL)
);

-- Hot-path partial index: the protected-set query reads
--   SELECT db_version, detail_index_url FROM catalog_releases WHERE state = 'ACTIVE'
-- on every cleanup run. Partial index keeps it cheap as RETIRED rows accumulate.
CREATE INDEX IF NOT EXISTS idx_catalog_releases_active
  ON catalog_releases (release_channel)
  WHERE state = 'ACTIVE';

-- General state index for audit queries (e.g. "show me all RETIRED releases").
CREATE INDEX IF NOT EXISTS idx_catalog_releases_state
  ON catalog_releases (state);

-- RLS: public read so consumer-side tooling can introspect; service-role only writes.
ALTER TABLE catalog_releases ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read catalog_releases" ON catalog_releases
  FOR SELECT TO anon, authenticated USING (true);
