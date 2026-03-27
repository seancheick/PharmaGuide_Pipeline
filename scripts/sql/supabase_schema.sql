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
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users NOT NULL,
  dsld_id      text NOT NULL,
  dosage       text,
  timing       text,
  supply_count integer,
  added_at     timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_usage (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users NOT NULL,
  scans_today       integer DEFAULT 0 CHECK (scans_today >= 0),
  ai_messages_today integer DEFAULT 0 CHECK (ai_messages_today >= 0),
  reset_date        date DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS pending_products (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users NOT NULL,
  upc          text NOT NULL,
  product_name text,
  brand        text,
  image_url    text,
  status       text DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'approved', 'rejected', 'duplicate')),
  submitted_at timestamptz DEFAULT now()
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_user_stacks_user ON user_stacks(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_stacks_user_dsld ON user_stacks(user_id, dsld_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_user ON user_usage(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_usage_daily ON user_usage(user_id, reset_date);
CREATE INDEX IF NOT EXISTS idx_pending_products_user ON pending_products(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_products_status ON pending_products(status) WHERE status = 'pending';

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

-- user_usage: users read/write own usage
ALTER TABLE user_usage ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own usage" ON user_usage
  FOR ALL USING ((SELECT auth.uid()) = user_id);

-- pending_products: users submit and view own submissions
ALTER TABLE pending_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own submissions" ON pending_products
  FOR ALL USING ((SELECT auth.uid()) = user_id);

-- =============================================================================
-- 6. RPC Functions
-- =============================================================================

-- 6a. Atomic manifest rotation (service_role only)
-- INSERT new row first, then UPDATE others — no window where zero are current.
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

-- 6b. Atomic usage increment with day rollover and server-side enforcement
-- Flutter calls after a successful scan or AI message.
CREATE OR REPLACE FUNCTION increment_usage(
  p_user_id uuid,
  p_type text  -- 'scan' or 'ai_message'
) RETURNS TABLE(scans_today integer, ai_messages_today integer, limit_exceeded boolean) AS $$
DECLARE
  v_scans integer;
  v_ai integer;
  v_exceeded boolean := false;
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
  INSERT INTO user_usage (user_id, scans_today, ai_messages_today, reset_date)
  VALUES (
    p_user_id,
    CASE WHEN p_type = 'scan' THEN 1 ELSE 0 END,
    CASE WHEN p_type = 'ai_message' THEN 1 ELSE 0 END,
    CURRENT_DATE
  )
  ON CONFLICT (user_id, reset_date)
  DO UPDATE SET
    scans_today = CASE WHEN p_type = 'scan'
      THEN user_usage.scans_today + 1
      ELSE user_usage.scans_today END,
    ai_messages_today = CASE WHEN p_type = 'ai_message'
      THEN user_usage.ai_messages_today + 1
      ELSE user_usage.ai_messages_today END;

  -- Read back current values
  SELECT u.scans_today, u.ai_messages_today
  INTO v_scans, v_ai
  FROM user_usage u
  WHERE u.user_id = p_user_id AND u.reset_date = CURRENT_DATE;

  -- Server-side limit enforcement (10 scans/day, 5 AI messages/day)
  IF (p_type = 'scan' AND v_scans > 10) OR (p_type = 'ai_message' AND v_ai > 5) THEN
    v_exceeded := true;
  END IF;

  RETURN QUERY SELECT v_scans, v_ai, v_exceeded;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant increment_usage to authenticated users only (not anon)
GRANT EXECUTE ON FUNCTION increment_usage(uuid, text) TO authenticated;

-- =============================================================================
-- 7. Storage Bucket
-- =============================================================================
-- Create via Supabase Dashboard or API:
--   Bucket name: pharmaguide
--   Public: true (read via anon key)
--   File size limit: 100MB (for the SQLite DB file)
--
-- Folder structure:
--   pharmaguide/v{version}/pharmaguide_core.db
--   pharmaguide/v{version}/details/{dsld_id}.json
