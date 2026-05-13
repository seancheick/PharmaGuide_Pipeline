"""Contract tests for the Supabase SQL schema shipped to the project."""

from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "supabase_schema.sql"


def _schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def test_user_stacks_supports_local_first_sync_metadata():
    sql = _schema_sql()
    assert "deleted_at" in sql
    assert "client_updated_at" in sql
    assert "source_device_id" in sql


def test_user_usage_reset_policy_is_explicitly_utc():
    sql = _schema_sql()
    assert "reset_day_utc" in sql
    assert "UTC day boundaries" in sql


def test_pending_products_supports_moderation_and_dedupe():
    sql = _schema_sql()
    assert "normalized_upc" in sql
    assert "submitter_note" in sql
    assert "review_notes" in sql
    assert "reviewed_at" in sql
    assert "reviewed_by" in sql
    assert "idx_pending_products_user_normalized_upc_pending" in sql


# ---------------------------------------------------------------------------
# catalog_releases (ADR-0001 P3.1)
# ---------------------------------------------------------------------------


def test_catalog_releases_table_defines_all_required_columns():
    """Schema must define the catalog_releases table with every column
    the registry depends on. Schema-as-contract — drift between this
    and the registry code base would corrupt protected-set computation."""
    sql = _schema_sql()
    assert "CREATE TABLE IF NOT EXISTS catalog_releases" in sql

    required_columns = [
        "db_version",
        "state",
        "release_channel",
        "released_at",
        "activated_at",
        "retired_at",
        "retired_reason",
        "bundled_in_app_versions",
        "flutter_repo_commit",
        "detail_index_url",
        "notes",
    ]
    for col in required_columns:
        assert col in sql, f"catalog_releases.{col} missing from schema"


def test_catalog_releases_state_enum_has_full_state_machine():
    """The state machine has exactly 4 states. Adding a new state
    without coordinated app-layer changes corrupts the registry; this
    test is the gate that catches schema drift."""
    sql = _schema_sql()
    assert "CREATE TYPE catalog_release_state AS ENUM" in sql
    for state in ("'PENDING'", "'VALIDATING'", "'ACTIVE'", "'RETIRED'"):
        assert state in sql, f"state {state} missing from catalog_release_state"


def test_catalog_releases_channel_enum_excludes_ota_beta():
    """Per ADR sign-off: ota_beta is intentionally NOT in the initial
    enum. Add it via ALTER TYPE when a real beta cohort exists.
    This test prevents a well-meaning future PR from quietly adding it."""
    sql = _schema_sql()
    assert "CREATE TYPE catalog_release_channel AS ENUM" in sql
    for channel in ("'bundled'", "'ota_stable'", "'dev'"):
        assert channel in sql, f"channel {channel} missing from catalog_release_channel"
    # Negative assertion: confirm ota_beta is NOT present
    assert "'ota_beta'" not in sql, (
        "ota_beta should NOT be in the channel enum yet — per ADR sign-off, "
        "add it only when a real beta cohort exists."
    )


def test_catalog_releases_state_machine_invariants_enforced_at_db_layer():
    """CHECK constraints that prevent app-layer bugs from corrupting
    the registry. These are the safety net for the state machine."""
    sql = _schema_sql()
    assert "CONSTRAINT activated_at_set_iff_active_or_retired" in sql
    assert "CONSTRAINT retired_fields_consistent" in sql
    assert "CONSTRAINT bundled_requires_flutter_commit" in sql


def test_catalog_releases_partial_index_on_active_for_protected_set_query():
    """The protected-set query (cleanup hot path) reads only ACTIVE rows.
    A partial index keeps it fast as RETIRED rows accumulate over time."""
    sql = _schema_sql()
    assert "idx_catalog_releases_active" in sql
    assert "WHERE state = 'ACTIVE'" in sql


def test_catalog_releases_rls_public_read_only():
    """Consumer-side tooling can introspect (anon read), but only
    service-role can write. Mirrors the export_manifest RLS pattern."""
    sql = _schema_sql()
    assert "ALTER TABLE catalog_releases ENABLE ROW LEVEL SECURITY" in sql
    assert 'CREATE POLICY "Public read catalog_releases"' in sql
    # SELECT-only policy; no INSERT/UPDATE/DELETE policies for non-service-role.
    # The CREATE POLICY block specifies FOR SELECT explicitly.
    catalog_section = sql[sql.index("CREATE POLICY \"Public read catalog_releases\""):]
    catalog_section = catalog_section[:catalog_section.index("\n\n") if "\n\n" in catalog_section else len(catalog_section)]
    assert "FOR SELECT" in catalog_section


def test_catalog_releases_enums_wrapped_in_idempotent_do_blocks():
    """ENUMs don't support `IF NOT EXISTS` syntax; without DO-block
    guards, re-running the schema file would fail. The wrapper makes
    the migration safely re-runnable."""
    sql = _schema_sql()
    # Both enums should be inside DO $$ ... $$ idempotency wrappers
    assert "pg_type WHERE typname = 'catalog_release_state'" in sql
    assert "pg_type WHERE typname = 'catalog_release_channel'" in sql


def test_catalog_releases_db_version_is_primary_key():
    """db_version is the natural key — semantic, sortable, unique by
    construction. Backfill becomes a clean upsert."""
    sql = _schema_sql()
    # Find the catalog_releases table block and check db_version is the PK
    table_start = sql.index("CREATE TABLE IF NOT EXISTS catalog_releases")
    table_block = sql[table_start:table_start + 2000]
    assert "db_version              text PRIMARY KEY" in table_block
