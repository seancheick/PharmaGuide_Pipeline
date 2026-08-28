"""Release orchestration must reject unreviewed scoring-snapshot drift."""

import subprocess
from pathlib import Path


RELEASE_SCRIPT = Path(__file__).parent.parent / "release_full.sh"
SNAPSHOT_SCRIPT = Path(__file__).parent.parent / "rebuild_dashboard_snapshot.sh"


def test_release_script_is_valid_bash_without_merge_markers():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    marker_lines = [
        line
        for line in source.splitlines()
        if line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
    ]
    assert marker_lines == []
    result = subprocess.run(
        ["bash", "-n", str(RELEASE_SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


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


def test_release_stamp_records_interaction_parity_only_after_its_gate():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    interaction_gate = source.index('run_strict_gate "interaction DB parity"')
    manifest_stamp = source.index(
        'run_strict_gate "stamp export manifest contract metadata"'
    )

    assert interaction_gate < manifest_stamp
    assert "--interaction-parity-verified" in source[
        manifest_stamp : source.index(
            'run_strict_gate "export contract"', manifest_stamp
        )
    ]


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


def test_banned_recalled_reference_change_forces_catalog_rebuild():
    """A safety-data edit cannot be skipped by auto-smart release freshness."""
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    assert 'BANNED_RECALLED_REFERENCE_SOURCE=' in source
    assert 'scripts/data/banned_recalled_ingredients.json' in source
    freshness_check = source.index('if is_path_newer_than "$BANNED_RECALLED_REFERENCE_SOURCE"')
    skip_branch = source.index('return 1  # safe to skip')
    assert freshness_check < skip_branch


def test_iqm_reference_change_forces_catalog_rebuild():
    """Form-note source changes must not reuse an older exported catalog."""
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    assert 'IQM_REFERENCE_SOURCE=' in source
    assert 'scripts/data/ingredient_quality_map.json' in source
    freshness_check = source.index('if is_path_newer_than "$IQM_REFERENCE_SOURCE"')
    skip_branch = source.index('return 1  # safe to skip')
    assert freshness_check < skip_branch


def test_safety_and_formulation_reference_changes_force_catalog_rebuild():
    """The assembled catalog embeds all three reference sources."""
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")
    skip_branch = source.index('return 1  # safe to skip')

    for variable, path in (
        ("HARMFUL_ADDITIVES_REFERENCE_SOURCE", "scripts/data/harmful_additives.json"),
        ("OTHER_INGREDIENTS_REFERENCE_SOURCE", "scripts/data/other_ingredients.json"),
        ("ABSORPTION_ENHANCERS_REFERENCE_SOURCE", "scripts/data/absorption_enhancers.json"),
    ):
        assert f'{variable}=' in source
        assert path in source
        freshness_check = source.index(f'if is_path_newer_than "${variable}"')
        assert freshness_check < skip_branch


def test_version_cleanup_is_separate_from_branch_aware_orphan_reconciliation():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    branch_resolution = source.index(
        'FLUTTER_RELEASE_BRANCH="$(git -C "$FLUTTER_REPO" branch --show-current)"'
    )
    bundle_commit = source.index(
        'git -C "$FLUTTER_REPO" commit -q -m "chore(catalog): bundle catalog'
    )
    cleanup = source.index('"$PG_PYTHON" scripts/cleanup_old_versions.py')

    assert branch_resolution < bundle_commit < cleanup
    cleanup_call = source[cleanup:source.index('; then', cleanup)]
    assert "--branch" not in cleanup_call
    assert "--flutter-repo" not in cleanup_call
    assert "--dist-dir" not in cleanup_call

    deferred_start = source.index('warn "Orphan cleanup: DEFERRED')
    deferred_end = source.index(
        "# A submission becomes user-visible", deferred_start,
    )
    deferred = source[deferred_start:deferred_end]
    assert "--branch" in deferred
    assert "FLUTTER_RELEASE_BRANCH" in deferred
