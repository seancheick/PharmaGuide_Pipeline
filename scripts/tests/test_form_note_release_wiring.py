"""Release wiring for the form-note artifact validator."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_paths_run_form_note_artifact_validator_before_publication():
    release = (REPO_ROOT / "scripts" / "release_full.sh").read_text()
    test_runner = (REPO_ROOT / "scripts" / "test.sh").read_text()
    snapshot = (REPO_ROOT / "scripts" / "rebuild_dashboard_snapshot.sh").read_text()

    assert "validate_form_notes_export.py --blobs-dir \"$DIST_DIR/detail_blobs\"" in release
    assert (
        'scripts/validate_form_notes_export.py --blobs-dir '
        '"$RELEASE_DIST_DIR/detail_blobs"'
    ) in test_runner
    assert release.index("validate_form_notes_export.py") < release.index(
        "scripts/sync_to_supabase.py \"$DIST_DIR\""
    )
    snapshot_gate = snapshot.index('run_strict_gate "form-note export artifact"')
    promotion = snapshot.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')
    assert 'validate_form_notes_export.py --blobs-dir "$DIST_CANDIDATE/detail_blobs"' in snapshot
    assert snapshot_gate < promotion
