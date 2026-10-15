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


def test_release_runs_catalog_change_gate_before_any_publication():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    gate = source.index('run_strict_gate "catalog changes vs what users have"')
    asset_publish = source.index('run_strict_gate "interaction DB release asset + app hydration pin"')
    supabase_sync = source.index("# Step 5: Sync to Supabase")

    assert gate < asset_publish < supabase_sync
    assert "scripts/release_safety/catalog_diff.py" in source[gate:asset_publish]


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
    assert source.count("SCORING_SNAPSHOT_GATE_RAN=1") == 1
    assert "if (( SCORING_SNAPSHOT_GATE_RAN == 0 )); then" in source
    assert "already passed before candidate promotion" in source


def test_identity_contract_gate_runs_even_when_catalog_is_fresh():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    identity_gate = source.index('run_strict_gate "active identity integrity"')
    freshness_branch = source.index('if step1_needs_run; then')

    publication = source.index("# Step 3: Extract/backfill DSLD product images")
    assert freshness_branch < identity_gate < publication
    assert '--export-dir "$DIST_DIR"' in source[identity_gate:publication]
    # Source invalidation is exercised through the actual content owner in
    # test_release_artifact_promotion, rather than pinning a shell path list.
    assert '--catalog-current' in source


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


def test_release_reuses_content_receipt_and_does_not_force_double_build():
    source = RELEASE_SCRIPT.read_text()
    start = source.index('step1_needs_run()')
    end = source.index('if step1_needs_run;')
    assert '--catalog-current' in source[start:end]
    assert 'any_pipeline_output_newer_than' not in source[start:end]
    assert 'step2_needs_run()' not in source


def test_release_reseals_only_after_owned_image_mutation_and_checks_before_upload():
    source = RELEASE_SCRIPT.read_text()
    images = source.index('sync_final_db_output_catalog_from_dist\n', source.index('# Step 3 mutates'))
    record = source.index('--record-catalog "$CATALOG_INPUT_BINDING"', images)
    check = source.index('--check-input-binding "$CATALOG_INPUT_BINDING"', record)
    upload = source.index('scripts/sync_to_supabase.py "$DIST_DIR"')
    assert images < record < check < upload


def test_cloud_only_publication_has_its_own_source_freeze_check():
    source = RELEASE_SCRIPT.read_text()
    step5 = source[source.index('if (( SKIP_SUPABASE == 0 )); then', source.index('# Step 5:')):]
    check = step5.index('--check-input-binding "$CATALOG_INPUT_BINDING"')
    upload = step5.index('scripts/sync_to_supabase.py "$DIST_DIR"\n')
    assert check < upload
    assert 'SKIP_FLUTTER' not in step5[:upload]


def test_catalog_staging_has_no_second_build_or_mtime_decision():
    source = RELEASE_SCRIPT.read_text()
    assert source.count('bash scripts/rebuild_dashboard_snapshot.sh') == 1
    assert 'step2_needs_run()' not in source
