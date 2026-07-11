"""Release orchestration must reject unreviewed scoring-snapshot drift."""

from pathlib import Path


RELEASE_SCRIPT = Path(__file__).parent.parent / "release_full.sh"


def test_release_runs_snapshot_contract_before_supabase_sync():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    snapshot_gate = source.index('run_strict_gate "scoring snapshot contract"')
    supabase_sync = source.index("# Step 5: Sync to Supabase")

    assert snapshot_gate < supabase_sync
    assert "scripts/tests/test_scoring_snapshot_v1.py" in source


def test_identity_contract_gate_runs_even_when_catalog_is_fresh():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    identity_gate = source.index('run_strict_gate "active identity integrity"')
    freshness_branch = source.index('if step1_needs_run; then')

    assert identity_gate < freshness_branch
    for path in (
        "scripts/audit_identity_integrity.py",
        "scripts/identity_integrity.py",
        "scripts/build_final_db.py",
        "scripts/scoring_input_contract.py",
        "scripts/scoring_v4/quality_score.py",
        "scripts/scoring_v4/pillar_explanations.py",
    ):
        assert path in source
