-- PharmaGuide Supabase Schema
-- Run this in the Supabase SQL Editor to set up the project.
-- Version: 2.0.0
-- Date: 2026-03-27
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

CREATE TABLE IF NOT EXISTS user_stacks (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users NOT NULL,
  dsld_id           text NOT NULL,
  dosage            text,
  timing            text,
  supply_count      integer,
  source_device_id  text,
  client_updated_at timestamptz,
  deleted_at        timestamptz,
  added_at          timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now()
);

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
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_stacks_user_dsld_active
  ON user_stacks(user_id, dsld_id)
  WHERE deleted_at IS NULL;
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
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_stacks_updated_at
  BEFORE UPDATE ON user_stacks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 5. Row Level Security
-- =============================================================================

-- export_manifest: anyone can read, only service role can write
ALTER TABLE export_manifest ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read manifest" ON export_manifest
  FOR SELECT USING (true);

-- user_stacks: users own their rows (SELECT auth.uid() pattern for performance)
ALTER TABLE user_stacks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own stacks" ON user_stacks
  FOR ALL USING ((SELECT auth.uid()) = user_id);

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
$$ LANGUAGE plpgsql SECURITY DEFINER;

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
$$ LANGUAGE plpgsql SECURITY DEFINER;

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
