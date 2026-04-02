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
