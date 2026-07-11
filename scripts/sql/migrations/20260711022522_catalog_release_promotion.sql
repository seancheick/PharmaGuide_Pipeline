-- =============================================================================
-- Atomic catalog release promotion (live migration 20260711022522)
-- =============================================================================
-- One release channel may have only one ACTIVE row. A client-side
-- VALIDATING -> ACTIVE followed by retirement of the predecessor violates that
-- invariant; reversing the writes creates an observable no-ACTIVE gap. Keep
-- both changes in one service-role-only database transaction instead.

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

  -- Read the target first only to discover the channel used for the scoped
  -- advisory lock. Re-read it under the lock before making any decision.
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

  -- Lock the active predecessor before changing it. The advisory lock makes
  -- simultaneous promotions for this channel serialize deterministically.
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
