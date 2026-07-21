"""Release orchestration must reject unreviewed scoring-snapshot drift."""

from pathlib import Path


RELEASE_SCRIPT = Path(__file__).parent.parent / "release_full.sh"
SNAPSHOT_SCRIPT = Path(__file__).parent.parent / "rebuild_dashboard_snapshot.sh"


def test_release_runs_snapshot_contract_before_supabase_sync():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    snapshot_gate = source.index('run_strict_gate "scoring snapshot contract"')
    supabase_sync = source.index("# Step 5: Sync to Supabase")

    assert snapshot_gate < supabase_sync
    assert "scripts/tests/test_scoring_snapshot_v1.py" in source


def test_release_preflights_flutter_import_before_supabase_sync():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    flutter_preflight = source.index(
        '"$FLUTTER_REPO/scripts/import_catalog_artifact.sh" "$DIST_DIR" --dry-run'
    )
    supabase_sync = source.index("# Step 5: Sync to Supabase")

    assert flutter_preflight < supabase_sync


def test_snapshot_contract_runs_before_candidate_promotion():
    source = SNAPSHOT_SCRIPT.read_text(encoding="utf-8")

    snapshot_gate = source.index('run_strict_gate "scoring snapshot contract"')
    candidate_build = source.index('"$PG_PYTHON" scripts/build_final_db.py')
    promotion = source.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')

    assert snapshot_gate < candidate_build < promotion


def test_release_does_not_repeat_snapshot_contract_after_snapshot_rebuild():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    assert "SCORING_SNAPSHOT_GATE_RAN=0" in source
    assert source.count("SCORING_SNAPSHOT_GATE_RAN=1") == 2
    assert "if (( SCORING_SNAPSHOT_GATE_RAN == 0 )); then" in source
    assert "already passed before candidate promotion" in source


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
