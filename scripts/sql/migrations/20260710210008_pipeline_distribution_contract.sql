-- =============================================================================
-- Pipeline distribution contract: integrity and least-privilege access
-- =============================================================================
-- This is the incremental migration for pipeline-owned public objects only:
-- export_manifest, catalog_releases, and rotate_manifest. Flutter migrations
-- own user_stacks, user_usage, pending_products, and increment_usage.
--
-- This migration fails rather than fabricating values or deleting releases.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.export_manifest
    WHERE is_current IS NULL
       OR product_count IS NULL
       OR product_count < 0
  ) THEN
    RAISE EXCEPTION
      'export_manifest contains nullable current-state or negative product counts';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.catalog_releases
    WHERE state NOT IN ('PENDING', 'VALIDATING')
      AND activated_at IS NULL
  ) THEN
    RAISE EXCEPTION
      'catalog_releases has ACTIVE or RETIRED rows without activated_at';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.catalog_releases
    WHERE (state = 'RETIRED' AND (retired_at IS NULL OR retired_reason IS NULL))
       OR (state <> 'RETIRED' AND (retired_at IS NOT NULL OR retired_reason IS NOT NULL))
  ) THEN
    RAISE EXCEPTION
      'catalog_releases has inconsistent retirement fields';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.catalog_releases
    WHERE release_channel = 'bundled'
      AND flutter_repo_commit IS NULL
  ) THEN
    RAISE EXCEPTION
      'catalog_releases has bundled rows without Flutter commit provenance';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.catalog_releases
    WHERE state = 'ACTIVE'
    GROUP BY release_channel
    HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION
      'catalog_releases has multiple ACTIVE releases in a channel; retire or correct them before enforcing uniqueness';
  END IF;
END
$$;

ALTER TABLE public.export_manifest
  ALTER COLUMN is_current SET NOT NULL,
  ALTER COLUMN product_count SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.export_manifest'::regclass
      AND conname = 'export_manifest_product_count_nonnegative_check'
  ) THEN
    ALTER TABLE public.export_manifest
      ADD CONSTRAINT export_manifest_product_count_nonnegative_check
      CHECK (product_count >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.catalog_releases'::regclass
      AND conname = 'activated_at_set_iff_active_or_retired'
  ) THEN
    ALTER TABLE public.catalog_releases
      ADD CONSTRAINT activated_at_set_iff_active_or_retired
      CHECK (state IN ('PENDING', 'VALIDATING') OR activated_at IS NOT NULL);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.catalog_releases'::regclass
      AND conname = 'retired_fields_consistent'
  ) THEN
    ALTER TABLE public.catalog_releases
      ADD CONSTRAINT retired_fields_consistent
      CHECK (
        (state = 'RETIRED' AND retired_at IS NOT NULL AND retired_reason IS NOT NULL)
        OR (state <> 'RETIRED' AND retired_at IS NULL AND retired_reason IS NULL)
      );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.catalog_releases'::regclass
      AND conname = 'bundled_requires_flutter_commit'
  ) THEN
    ALTER TABLE public.catalog_releases
      ADD CONSTRAINT bundled_requires_flutter_commit
      CHECK (release_channel <> 'bundled' OR flutter_repo_commit IS NOT NULL);
  END IF;
END
$$;

DROP INDEX IF EXISTS public.idx_catalog_releases_active;
CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_releases_active
  ON public.catalog_releases(release_channel)
  WHERE state = 'ACTIVE';

ALTER TABLE public.export_manifest ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read manifest" ON public.export_manifest;
CREATE POLICY "Public read manifest" ON public.export_manifest
  FOR SELECT TO anon, authenticated
  USING (true);

ALTER TABLE public.catalog_releases ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read catalog_releases" ON public.catalog_releases;
CREATE POLICY "Public read catalog_releases" ON public.catalog_releases
  FOR SELECT TO anon, authenticated
  USING (true);

REVOKE ALL ON TABLE public.export_manifest FROM anon, authenticated;
REVOKE ALL ON TABLE public.catalog_releases FROM anon, authenticated;
GRANT SELECT ON TABLE public.export_manifest TO anon, authenticated;
GRANT SELECT ON TABLE public.catalog_releases TO anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated;

REVOKE ALL ON FUNCTION public.rotate_manifest(text, text, text, text, integer, text, timestamptz, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.rotate_manifest(text, text, text, text, integer, text, timestamptz, text)
  TO service_role;
