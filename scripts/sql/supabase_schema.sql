-- PharmaGuide Supabase Schema
-- Run this in the Supabase SQL Editor to set up the project.
-- Version: 1.0.0
-- Date: 2026-03-27

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
  added_at     timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_usage (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users NOT NULL,
  scans_today       integer DEFAULT 0,
  ai_messages_today integer DEFAULT 0,
  reset_date        date DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS pending_products (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users NOT NULL,
  upc          text NOT NULL,
  product_name text,
  brand        text,
  image_url    text,
  status       text DEFAULT 'pending',
  submitted_at timestamptz DEFAULT now()
);

-- =============================================================================
-- 3. Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_user_stacks_user ON user_stacks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_user ON user_usage(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_usage_daily ON user_usage(user_id, reset_date);
CREATE INDEX IF NOT EXISTS idx_pending_products_user ON pending_products(user_id);

-- Partial index on export_manifest: only indexes is_current=true rows.
-- The app and sync script both query WHERE is_current = true on every launch.
-- Table grows one row per pipeline run indefinitely, so this stays fast.
CREATE INDEX IF NOT EXISTS idx_export_manifest_current
  ON export_manifest(is_current)
  WHERE is_current = true;

-- =============================================================================
-- 4. Row Level Security
-- =============================================================================

-- export_manifest: anyone can read, only service role can write
ALTER TABLE export_manifest ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read manifest" ON export_manifest
  FOR SELECT USING (true);

-- user_stacks: users own their rows
ALTER TABLE user_stacks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own stacks" ON user_stacks
  FOR ALL USING (auth.uid() = user_id);

-- user_usage: users read/write own usage
ALTER TABLE user_usage ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own usage" ON user_usage
  FOR ALL USING (auth.uid() = user_id);

-- pending_products: users submit and view own submissions
ALTER TABLE pending_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own submissions" ON pending_products
  FOR ALL USING (auth.uid() = user_id);

-- =============================================================================
-- 5. RPC Functions
-- =============================================================================

-- Atomic manifest rotation: INSERT new row first, then UPDATE others.
-- Ensures there is always at least one current row (no window where zero are current).
CREATE OR REPLACE FUNCTION rotate_manifest(
  p_db_version text,
  p_pipeline_version text,
  p_scoring_version text,
  p_schema_version text,
  p_product_count integer,
  p_checksum text,
  p_generated_at timestamptz
) RETURNS uuid AS $$
DECLARE
  new_id uuid;
BEGIN
  INSERT INTO export_manifest (
    db_version, pipeline_version, scoring_version, schema_version,
    product_count, checksum, generated_at, is_current
  ) VALUES (
    p_db_version, p_pipeline_version, p_scoring_version, p_schema_version,
    p_product_count, p_checksum, p_generated_at, true
  ) RETURNING id INTO new_id;

  UPDATE export_manifest
  SET is_current = false
  WHERE is_current = true AND id != new_id;

  RETURN new_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Atomic usage increment with automatic day rollover.
-- A new day means a new CURRENT_DATE — the unique index conflict never fires,
-- so a fresh row gets inserted with count 1. No manual read-then-write needed.
-- Flutter calls this RPC after a successful scan or AI message.
CREATE OR REPLACE FUNCTION increment_usage(
  p_user_id uuid,
  p_type text  -- 'scan' or 'ai_message'
) RETURNS TABLE(scans_today integer, ai_messages_today integer) AS $$
BEGIN
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

  RETURN QUERY
    SELECT u.scans_today, u.ai_messages_today
    FROM user_usage u
    WHERE u.user_id = p_user_id AND u.reset_date = CURRENT_DATE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

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
