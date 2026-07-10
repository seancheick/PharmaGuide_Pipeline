from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_pipeline_schema_does_not_own_app_usage_limits():
    sql = read("scripts/sql/supabase_schema.sql")
    assert "v_scan_limit constant integer" not in sql
    assert "v_ai_limit constant integer" not in sql
    assert "increment_usage" not in sql
