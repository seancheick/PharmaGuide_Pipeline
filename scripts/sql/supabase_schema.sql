-- PharmaGuide Supabase Schema
-- Run this in the Supabase SQL Editor to set up the project.
-- Version: 2.2.0
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
  product_count    integer NOT NULL CHECK (product_count >= 0),
  checksum         text NOT NULL,
  min_app_version  text NOT NULL DEFAULT '1.0.0',
  generated_at     timestamptz NOT NULL,
  created_at       timestamptz DEFAULT now(),
  is_current       boolean NOT NULL DEFAULT true
);

-- =============================================================================
-- 2. Pipeline Distribution Indexes
-- =============================================================================

-- Partial unique index: enforces exactly one is_current=true row at any time.
-- Prevents split-brain if rotate_manifest is called concurrently.
CREATE UNIQUE INDEX IF NOT EXISTS idx_export_manifest_one_current
  ON export_manifest((true))
  WHERE is_current = true;

-- =============================================================================
-- 3. Pipeline Distribution Access
-- =============================================================================

-- export_manifest: anyone can read, only service role can write
ALTER TABLE export_manifest ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read manifest" ON export_manifest;
CREATE POLICY "Public read manifest" ON export_manifest
  FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON TABLE export_manifest FROM anon, authenticated;
GRANT SELECT ON TABLE export_manifest TO anon, authenticated;

-- This deployment root owns the database-wide default access baseline. New
-- public objects receive no client access unless their owning schema grants it
-- explicitly. The Flutter migration grants app-table access; this file grants
-- distribution-table access above. Project DDL runs as postgres, which owns
-- every application table and function audited for this deployment.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated;

-- =============================================================================
-- 4. Pipeline RPC Functions
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
--   - Unique partial index on ACTIVE keeps the protected-set query (the hot path)
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

-- A channel may expose one active release at a time. Different channels can
-- be active concurrently (bundled, ota_stable, dev), but duplicate active
-- rows in one channel would make the release resolver ambiguous.
DROP INDEX IF EXISTS idx_catalog_releases_active;
CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_releases_active
  ON catalog_releases (release_channel)
  WHERE state = 'ACTIVE';

-- The unique active-channel index above also serves the protected-set query:
--   SELECT db_version, detail_index_url FROM catalog_releases WHERE state = 'ACTIVE'
-- It stays small as RETIRED rows accumulate.

-- General state index for audit queries (e.g. "show me all RETIRED releases").
CREATE INDEX IF NOT EXISTS idx_catalog_releases_state
  ON catalog_releases (state);

-- RLS: public read so consumer-side tooling can introspect; service-role only writes.
ALTER TABLE catalog_releases ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read catalog_releases" ON catalog_releases;
CREATE POLICY "Public read catalog_releases" ON catalog_releases
  FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON TABLE catalog_releases FROM anon, authenticated;
GRANT SELECT ON TABLE catalog_releases TO anon, authenticated;

-- Atomic channel promotion keeps the one-ACTIVE-row invariant without a
-- client-side activate/retire race or an observable no-ACTIVE interval.
CREATE OR REPLACE FUNCTION public.promote_catalog_release(
  p_db_version text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
DECLARE
  v_target public.catalog_releases%ROWTYPE;
  v_retired_count integer := 0;
BEGIN
  IF current_setting('request.jwt.claims', true)::json->>'role' IS DISTINCT FROM 'service_role' THEN
    RAISE EXCEPTION 'promote_catalog_release is restricted to service_role';
  END IF;

  SELECT *
    INTO v_target
    FROM public.catalog_releases
   WHERE db_version = p_db_version;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'catalog release % does not exist', p_db_version;
  END IF;

  PERFORM pg_advisory_xact_lock(hashtext(v_target.release_channel::text));

  SELECT *
    INTO v_target
    FROM public.catalog_releases
   WHERE db_version = p_db_version
   FOR UPDATE;

  IF v_target.state = 'ACTIVE' THEN
    RETURN jsonb_build_object(
      'db_version', v_target.db_version,
      'state', v_target.state,
      'already_active', true,
      'retired_count', 0
    );
  END IF;

  IF v_target.state <> 'VALIDATING' THEN
    RAISE EXCEPTION
      'catalog release % must be VALIDATING or ACTIVE before promotion; found %',
      p_db_version,
      v_target.state;
  END IF;

  PERFORM 1
    FROM public.catalog_releases
   WHERE release_channel = v_target.release_channel
     AND state = 'ACTIVE'
     AND db_version <> p_db_version
   FOR UPDATE;

  UPDATE public.catalog_releases
     SET state = 'RETIRED',
         retired_at = now(),
         retired_reason = format('superseded by active release %s', p_db_version)
   WHERE release_channel = v_target.release_channel
     AND state = 'ACTIVE'
     AND db_version <> p_db_version;
  GET DIAGNOSTICS v_retired_count = ROW_COUNT;

  UPDATE public.catalog_releases
     SET state = 'ACTIVE',
         activated_at = COALESCE(activated_at, now())
   WHERE db_version = p_db_version
     AND state = 'VALIDATING'
  RETURNING * INTO v_target;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'catalog release % changed during promotion', p_db_version;
  END IF;

  RETURN jsonb_build_object(
    'db_version', v_target.db_version,
    'state', v_target.state,
    'already_active', false,
    'retired_count', v_retired_count
  );
END;
$$;

REVOKE ALL ON FUNCTION public.promote_catalog_release(text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.promote_catalog_release(text)
  TO service_role;

-- =============================================================================
-- 9. Public catalog search (read only by the public MCP edge function)
-- =============================================================================
-- One slim row per product per catalog release, published by
-- sync_to_supabase.py::publish_catalog_search from the release's
-- pharmaguide_core.db BEFORE rotate_manifest runs. Readers use
-- catalog_search_current, which joins export_manifest.is_current, so a
-- version that is still uploading (or an older one kept for rollback) is never
-- visible. upc_sku is stored with the app's normalization (spaces, '-', '.',
-- '/' removed; Flutter CoreDatabase.upcNormalizeSql) so a barcode lookup is an
-- exact match. No client role reads these objects: the public MCP function
-- reads with the service role. Product discovery only; no personal data.

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS public.catalog_search (
  catalog_version          text NOT NULL,
  dsld_id                  text NOT NULL,
  product_name             text NOT NULL,
  brand_name               text,
  brand_family             text,
  product_line             text,
  upc_sku                  text,
  form_factor              text,
  supplement_type          text,
  product_status           text,
  quality_tier             text,
  quality_score_status     text,
  quality_score_v4_100     double precision CHECK (quality_score_v4_100 BETWEEN 0 AND 100),
  product_safety_status    text,
  -- The detail blob carries neither mapped_coverage nor quality_score_confidence;
  -- quality_assessment_status lets search results apply the completion rule.
  mapped_coverage          double precision
    CHECK (mapped_coverage IS NULL OR (mapped_coverage >= 0 AND mapped_coverage <= 1)),
  quality_score_confidence text,
  quality_assessment_status text,
  search_tsv               tsvector GENERATED ALWAYS AS (
    to_tsvector(
      'simple'::regconfig,
      coalesce(product_name, '') || ' ' || coalesce(brand_name, '') || ' ' ||
      coalesce(product_line, '')
    )
  ) STORED,
  published_at             timestamptz DEFAULT now(),
  PRIMARY KEY (catalog_version, dsld_id)
);

CREATE INDEX IF NOT EXISTS idx_catalog_search_product_name_trgm
  ON public.catalog_search USING gin (product_name extensions.gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_catalog_search_brand_name_trgm
  ON public.catalog_search USING gin (brand_name extensions.gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_catalog_search_tsv
  ON public.catalog_search USING gin (search_tsv);
CREATE INDEX IF NOT EXISTS idx_catalog_search_upc_sku
  ON public.catalog_search (upc_sku)
  WHERE upc_sku IS NOT NULL;

ALTER TABLE public.catalog_search ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.catalog_search FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.catalog_search TO service_role;

CREATE OR REPLACE VIEW public.catalog_search_current
  WITH (security_invoker = true) AS
SELECT cs.catalog_version,
       cs.dsld_id,
       cs.product_name,
       cs.brand_name,
       cs.brand_family,
       cs.product_line,
       cs.upc_sku,
       cs.form_factor,
       cs.supplement_type,
       cs.product_status,
       cs.quality_tier,
       cs.quality_score_status,
       cs.product_safety_status,
       cs.mapped_coverage,
       cs.quality_score_confidence,
       cs.quality_assessment_status,
       cs.search_tsv,
       cs.quality_score_v4_100
  FROM public.catalog_search cs
  JOIN public.export_manifest m
    ON m.db_version = cs.catalog_version
   AND m.is_current = true;

REVOKE ALL ON TABLE public.catalog_search_current FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.catalog_search_current TO service_role;
-- security_invoker view: its reader also needs the manifest it joins.
GRANT SELECT ON TABLE public.export_manifest TO service_role;

-- Ranked search for the public MCP `search_products` tool. Trigram similarity
-- (typo tolerant) blended with a full-text rank; match_score is in [0, 1].
-- SECURITY INVOKER: it can only ever see what its caller (service_role) sees.
CREATE OR REPLACE FUNCTION public.search_catalog(
  p_query text,
  p_brand text DEFAULT NULL,
  p_form  text DEFAULT NULL,
  p_limit integer DEFAULT 10,
  p_sort text DEFAULT 'relevance',
  p_offset integer DEFAULT 0,
  p_catalog_version text DEFAULT NULL,
  p_supplement_type text DEFAULT NULL
)
RETURNS TABLE (
  catalog_version          text,
  dsld_id                  text,
  product_name             text,
  brand_name               text,
  brand_family             text,
  product_line             text,
  upc_sku                  text,
  form_factor              text,
  supplement_type          text,
  product_status           text,
  quality_tier             text,
  quality_score_status     text,
  product_safety_status    text,
  mapped_coverage          double precision,
  quality_score_confidence text,
  quality_assessment_status text,
  match_score              real,
  quality_score_v4_100     double precision,
  total_matches           bigint
)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public, extensions, pg_catalog
AS $$
  WITH q AS (
    SELECT lower(left(btrim(coalesce(p_query, '')), 200)) AS text,
           websearch_to_tsquery('simple'::regconfig, left(btrim(coalesce(p_query, '')), 200)) AS tsq
  )
  SELECT c.catalog_version, c.dsld_id, c.product_name, c.brand_name, c.brand_family,
         c.product_line, c.upc_sku, c.form_factor, c.supplement_type, c.product_status,
         c.quality_tier, c.quality_score_status, c.product_safety_status,
         c.mapped_coverage, c.quality_score_confidence, c.quality_assessment_status,
         LEAST(1.0,
           GREATEST(
             extensions.similarity(c.product_name, q.text),
             extensions.word_similarity(
               q.text, concat_ws(' ', c.brand_name, c.product_name, c.product_line))
           ) * 0.8
           + ts_rank_cd(c.search_tsv, q.tsq, 32) * 0.2
         )::real AS match_score,
         c.quality_score_v4_100, count(*) OVER () AS total_matches
    FROM public.catalog_search_current c, q
   WHERE length(q.text) > 0
     AND p_sort IN ('relevance', 'quality')
     AND (p_supplement_type IS NULL OR c.supplement_type = p_supplement_type)
     AND (p_catalog_version IS NULL OR c.catalog_version = p_catalog_version)
     AND (c.search_tsv @@ q.tsq OR q.text <% c.product_name OR q.text <% c.brand_name)
     AND (p_brand IS NULL OR strpos(lower(concat_ws(' ', c.brand_name, c.brand_family)),
                                    lower(btrim(p_brand))) > 0)
     AND (p_form IS NULL OR strpos(lower(coalesce(c.form_factor, '')), lower(btrim(p_form))) > 0)
   ORDER BY CASE WHEN p_sort = 'quality' AND c.quality_score_status = 'scored'
                       AND c.quality_assessment_status = 'complete'
                 THEN c.quality_score_v4_100 END DESC NULLS LAST,
            match_score DESC, c.dsld_id
   LIMIT LEAST(GREATEST(coalesce(p_limit, 10), 1), 25)
   OFFSET GREATEST(coalesce(p_offset, 0), 0);
$$;

REVOKE ALL ON FUNCTION public.search_catalog(text, text, text, integer, text, integer, text, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.search_catalog(text, text, text, integer, text, integer, text, text)
  TO service_role;
