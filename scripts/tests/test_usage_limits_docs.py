from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_supabase_schema_uses_20_scan_and_5_ai_signed_in_limits():
    sql = read("scripts/sql/supabase_schema.sql")
    assert "v_scan_limit constant integer := 20;" in sql
    assert "v_ai_limit constant integer := 5;" in sql
    assert "v_scan_limit constant integer := 10;" not in sql


def test_flutter_docs_reflect_guest_10_lifetime_and_signed_in_20_per_day_policy():
    contract = read("scripts/FLUTTER_DATA_CONTRACT_V1.md")
    mvp = read("scripts/PharmaGuide Flutter MVP Dev.md")
    flutter_spec = read("docs/superpowers/specs/2026-03-29-flutter-app-build-design.md")

    assert "10 lifetime" in contract or "10 lifetime" in mvp or "10 lifetime" in flutter_spec
    assert "20 scans/day" in contract
    assert "5 AI/day" in contract

    assert "Guest: 10 scans lifetime" in mvp
    assert "Signed In (free): 20 scans/day." in mvp
    assert "AI Chat: 5 messages/day" in mvp

    assert "Guest: Hive guest_scan_count, >= 10" in flutter_spec
    assert "If scans_today >= 20" in flutter_spec
    assert "5/day via increment_usage RPC" in flutter_spec

    assert "3 scans lifetime" not in mvp
    assert ">= 3 -> upgrade sheet" not in flutter_spec
