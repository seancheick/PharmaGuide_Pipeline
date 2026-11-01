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
    cleanup = source.index('warn "Version cleanup: DEFERRED')

    assert branch_resolution < bundle_commit < cleanup
    cleanup_call = source[cleanup:source.index('warn "Orphan cleanup: DEFERRED', cleanup)]
    assert "--execute --cleanup-db --keep" in cleanup_call
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
    upload_only = step5.index('Step 5/8: Syncing dist/ to Supabase (upload only; cleanup deferred)')
    upload = step5.index('scripts/sync_to_supabase.py "$DIST_DIR"', upload_only)
    assert check < upload
    assert 'SKIP_FLUTTER' not in step5[:upload]


def test_catalog_staging_has_no_second_build_or_mtime_decision():
    source = RELEASE_SCRIPT.read_text()
    assert source.count('bash scripts/rebuild_dashboard_snapshot.sh') == 1
    assert 'step2_needs_run()' not in source


def test_completed_manifest_is_sealed_before_a_review_hold_can_exit():
    source = RELEASE_SCRIPT.read_text()
    stamp = source.index('run_strict_gate "stamp export manifest contract metadata"')
    comparison = source.index('run_strict_gate "catalog changes vs what users have"')
    seal = source.index('--record-catalog "$CATALOG_INPUT_BINDING"', stamp)
    # A review hold exits the shell. Preserve the validated metadata in the
    # content receipt first, so retrying cannot rebuild a new hash to approve.
    assert stamp < seal < comparison
    publication = source.index('run_strict_gate "interaction DB release asset + app hydration pin"')
    assert comparison < source.index('--check-input-binding "$CATALOG_INPUT_BINDING"', comparison) < publication


def test_release_runs_strict_assessment_audit_after_optional_snapshot_before_publication():
    source = RELEASE_SCRIPT.read_text(encoding='utf-8')
    gate = source.index('run_strict_gate "scoring assessment completion contract"')
    publication = source.index('run_strict_gate "interaction DB release asset + app hydration pin"')
    assert gate < publication
    command = source[gate:source.index('run_strict_gate "clinical drift contract"', gate)]
    assert 'scoring --products-dir "$PRODUCTS_DIR" --dist-dir "$DIST_DIR" --strict-release' in command
    # This sits among unconditional final gates, after all snapshot/reuse branches.
    cleaner = source.index('run_strict_gate "cleaner/IQD row contract"')
    assert cleaner < gate
    assert '\nif ' not in source[cleaner:gate]


def test_snapshot_unfinished_completion_stops_before_builder(tmp_path):
    source = SNAPSHOT_SCRIPT.read_text()
    # Execute the real preassembly gate block with bounded gate stubs.
    gates = source[source.index('run_strict_gate "raw DSLD label availability"'):
                   source.index('# 1. Collect enriched + scored dirs.')]
    script = '''set -euo pipefail
REPO_ROOT=repo
PG_PYTHON=python
SOURCE_OF_TRUTH_AUDIT=audit.py
RAW_ROOT=raw
run_strict_gate() {
  if [[ "$1" == "scoring assessment completeness preflight" ]]; then
    [[ "$*" == *"--completion-only"* ]] || exit 99
    return 37
  fi
}
''' + gates + '\nprintf builder_reached\n'
    result = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
    assert result.returncode == 37, result.stdout + result.stderr
    assert 'builder_reached' not in result.stdout
    # Candidate-sensitive checks are still unconditional after assembly.
    build = source.index('"$PG_PYTHON" scripts/build_final_db.py')
    assert source.index('run_strict_gate "scoring assessment readiness"') > build
    assert source.index('run_strict_gate "active identity integrity"') > build
    assert source.index('run_strict_gate "raw-to-final line integrity"') > build


def _run_publication_failure_boundary(tmp_path, *, sync_exit=0, import_exit=23,
                                      before_sync_exit=0, skip_cloud=0, dry_run=0):
    import shlex
    source = RELEASE_SCRIPT.read_text()
    # Execute real release state handling and the real sync/import boundary.
    helpers = source[source.index('info()'):source.index('DIST_DIR="$REPO_ROOT/scripts/dist"')]
    boundary = source[source.index('# Step 5: Sync to Supabase'):source.index('# Step 7: Prune')]
    app = tmp_path / 'app'
    (app / 'scripts').mkdir(parents=True)
    importer = app / 'scripts/import_catalog_artifact.sh'
    importer.write_text(f'#!/bin/bash\nprintf "IMPORT_ATTEMPTED\\n"\nexit {import_exit}\n')
    importer.chmod(0o755)
    setup = f'''set -Eeuo pipefail
SKIP_SUPABASE={skip_cloud}
SUPABASE_DRY_RUN={dry_run}
SKIP_FLUTTER=0
FORCE=1
FLUTTER_REPO={shlex.quote(str(app))}
DIST_DIR=dist
ASSETS_DIR=assets
SUBMISSION_RECEIPTS=absent
SUBMISSION_OUTPUT_DIR=submissions
SOURCE_OF_TRUTH_AUDIT=audit
CATALOG_STATE_SCRIPT=state
CATALOG_INPUT_BINDING=binding
PG_PYTHON=python_gate
python_gate() {{
  if [[ "$1" == state ]]; then return {before_sync_exit}; fi
  if [[ "$1" == scripts/sync_to_supabase.py ]]; then
    printf 'SYNC_ATTEMPTED\\n'
    return {sync_exit}
  fi
  return 0
}}
run_strict_gate() {{
  local label="$1"; shift
  case "$label" in
    "Supabase catalog sync"|"Flutter bundle import") "$@" ;;
    *) return 0 ;;
  esac
}}
'''
    return subprocess.run(['bash', '-c', setup + helpers + boundary + '\necho RELEASE_FINISHED\n'],
                          text=True, capture_output=True)


def test_failed_flutter_import_reports_confirmed_cloud_state(tmp_path):
    result = _run_publication_failure_boundary(tmp_path)
    assert result.returncode == 23
    assert 'SYNC_ATTEMPTED' in result.stdout and 'IMPORT_ATTEMPTED' in result.stdout
    assert 'Supabase catalog sync completed successfully' in result.stderr
    assert 'Flutter bundle' in result.stderr
    assert 'RELEASE_FINISHED' not in result.stdout


def test_failed_sync_does_not_claim_activation_failed_or_succeeded(tmp_path):
    result = _run_publication_failure_boundary(tmp_path, sync_exit=37)
    assert result.returncode == 37
    assert 'activation outcome is unknown' in result.stderr
    assert 'IMPORT_ATTEMPTED' not in result.stdout
    assert 'sync completed successfully' not in result.stderr


def test_pre_sync_failure_reports_publication_not_attempted(tmp_path):
    result = _run_publication_failure_boundary(tmp_path, before_sync_exit=29)
    assert result.returncode == 29
    assert 'catalog publication was not attempted' in result.stderr
    assert 'SYNC_ATTEMPTED' not in result.stdout


def test_local_import_failure_after_dry_run_does_not_claim_publication(tmp_path):
    result = _run_publication_failure_boundary(tmp_path, dry_run=1)
    assert result.returncode == 23
    assert 'catalog publication was not attempted' in result.stderr
    assert 'sync completed successfully' not in result.stderr


def test_local_import_failure_with_cloud_skipped_does_not_claim_publication(tmp_path):
    result = _run_publication_failure_boundary(tmp_path, skip_cloud=1)
    assert result.returncode == 23
    assert 'catalog publication was not attempted' in result.stderr
    assert 'SYNC_ATTEMPTED' not in result.stdout


def test_successful_publication_boundary_has_no_failure_report(tmp_path):
    result = _run_publication_failure_boundary(tmp_path, import_exit=0)
    assert result.returncode == 0
    assert 'RELEASE_FINISHED' in result.stdout
    assert 'Release incomplete' not in result.stderr


def test_release_handoff_respects_required_main_checks():
    source = RELEASE_SCRIPT.read_text()
    handoff = source[source.index('info "Next steps'):]
    assert 'git push origin main' not in handoff
    assert 'git push -u origin HEAD' in handoff
    assert 'Merge readiness' in handoff
    assert 'gh pr create --base main' in handoff
