"""Release orchestration must reject unreviewed scoring-snapshot drift."""

from pathlib import Path


RELEASE_SCRIPT = Path(__file__).parent.parent / "release_full.sh"


def test_release_runs_snapshot_contract_before_supabase_sync():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    snapshot_gate = source.index('run_strict_gate "scoring snapshot contract"')
    supabase_sync = source.index("# Step 5: Sync to Supabase")

    assert snapshot_gate < supabase_sync
    assert "scripts/tests/test_scoring_snapshot_v1.py" in source
