from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "rebuild_dashboard_snapshot.sh"


def test_snapshot_gates_candidates_before_live_promotion() -> None:
    source = SCRIPT.read_text()

    promotion = source.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')
    freshness_gate = source.index('run_strict_gate "catalog artifact freshness"')
    candidate_stage = source.index("--output-dir \"$DIST_CANDIDATE\"")

    assert candidate_stage < freshness_gate < promotion
    assert "--output-dir scripts/dist" not in source
    assert "rm -rf scripts/final_db_output" not in source
    assert source.rindex("run_strict_gate", 0, promotion) < promotion


def test_source_gates_run_before_catalog_build() -> None:
    source = SCRIPT.read_text()
    build = source.index('"$PG_PYTHON" scripts/build_final_db.py')

    for label in (
        'run_strict_gate "source-of-truth matrix"',
        'run_strict_gate "cleaner/IQD row contract"',
        'run_strict_gate "enrichment/IQD source-of-truth contract"',
        'run_strict_gate "clinical drift contract"',
        'run_strict_gate "RDA/UL emitted-reference stamp parity"',
    ):
        assert source.index(label) < build


def test_identity_gate_proves_candidate_exclusion_before_promotion() -> None:
    source = SCRIPT.read_text()
    build = source.index('"$PG_PYTHON" scripts/build_final_db.py')
    identity = source.index('run_strict_gate "active identity integrity"')
    promotion = source.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')
    assert build < identity < promotion
    assert '--export-dir "$FINAL_CANDIDATE"' in source[identity:promotion]
    scoring = source.index('run_strict_gate "scoring assessment readiness"')
    assert build < scoring < promotion
    assert '--dist-dir "$FINAL_CANDIDATE"' in source[scoring:promotion]


def test_candidate_only_mode_preserves_gated_artifacts_without_live_promotion() -> None:
    source = SCRIPT.read_text()

    assert "--candidate-only" in source
    assert "--candidate-root" in source
    assert '[[ "$CANDIDATE_ROOT" = /* ]]' in source
    assert '[[ ! -e "$CANDIDATE_ROOT" ]]' in source

    candidate_branch = source.index(
        'if [[ "$CANDIDATE_ONLY" == "true" ]]; then',
        source.index('run_strict_gate "catalog artifact freshness"'),
    )
    promotion = source.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')

    assert candidate_branch < promotion
    assert 'mv "$CANDIDATE_STAGE" "$CANDIDATE_ROOT"' in source
    assert 'DIST_OUTPUT="$CANDIDATE_ROOT/dist"' in source
    assert 'FINAL_OUTPUT="$CANDIDATE_ROOT/final_db_output"' in source


def test_snapshot_build_uses_strict_export_error_gate() -> None:
    source = SCRIPT.read_text()
    build_start = source.index('"$PG_PYTHON" scripts/build_final_db.py')
    build_end = source.index('run_strict_gate "detail-blob field completeness"')

    assert "--strict" in source[build_start:build_end]


def test_snapshot_does_not_discard_product_failure_diagnostics() -> None:
    source = SCRIPT.read_text()
    assert "| tail" not in source


def test_snapshot_freezes_inputs_before_build_and_checks_before_promotion():
    source = SCRIPT.read_text()
    freeze = source.index('--catalog-input-binding')
    build = source.index('"$PG_PYTHON" scripts/build_final_db.py')
    check = source.index('--check-input-binding "$CATALOG_INPUT_BINDING"')
    promote = source.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')
    assert freeze < build < check < promote
    assert source.index('--check-disk') < build
    assert source.index('--record-catalog "$CATALOG_INPUT_BINDING"') > promote


def test_standalone_snapshot_uses_existing_release_lock_before_any_build():
    source = SCRIPT.read_text()
    assert 'SNAPSHOT_ARGS=("$REPO_ROOT/scripts/rebuild_dashboard_snapshot.sh" "$@")' in source
    lock = source.index('scripts/run_with_release_lock.py')
    assert lock < source.index('--catalog-input-binding')
    assert '-- bash "${SNAPSHOT_ARGS[@]}"' in source


@pytest.mark.parametrize("script_name", ["rebuild_dashboard_snapshot.sh", "release_full.sh"])
def test_snapshot_lock_reentry_works_when_started_from_scripts_directory(tmp_path, script_name):
    import shutil
    import subprocess
    import sys
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    shutil.copy(SCRIPT.parent / script_name, scripts / script_name)
    (scripts / 'python_env.sh').write_text(f'PG_PYTHON="{sys.executable}"\n')
    (scripts / 'run_with_release_lock.py').write_text(
        'import sys\nfrom pathlib import Path\n'
        'child=sys.argv[sys.argv.index("--")+2]\n'
        'assert Path(child).is_absolute() and Path(child).is_file(), child\n'
    )
    result = subprocess.run(['bash', script_name], cwd=scripts, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_raw_to_final_line_gate_runs_on_every_candidate_before_promotion() -> None:
    source = SCRIPT.read_text()
    build = source.index('"$PG_PYTHON" scripts/build_final_db.py')
    line = source.index('run_strict_gate "raw-to-final line integrity"')
    promotion = source.index('"$PG_PYTHON" scripts/promote_release_artifacts.py')
    assert build < line < promotion
    gate = source[line:source.index("run_strict_gate", line + 1)]
    assert "scripts/audit_raw_to_final.py" in gate
    assert '--build-dir "$FINAL_CANDIDATE"' in gate
    assert "--all" in gate and "--canary" not in gate


def test_scoring_static_gate_runs_before_catalog_build() -> None:
    source = SCRIPT.read_text()
    static = source.index('run_strict_gate "strict scoring static reads"')
    assert static < source.index('"$PG_PYTHON" scripts/build_final_db.py')
    assert "scoring-static --strict-release" in source[static:static + 200]


def _gate_block(source: str, label: str) -> str:
    start = source.index(f'run_strict_gate "{label}"')
    return source[start:source.index("run_strict_gate", start + 1)]


def test_raw_label_availability_is_checked_before_any_expensive_snapshot_work() -> None:
    source = SCRIPT.read_text()
    availability = source.index('run_strict_gate "raw DSLD label availability"')
    first_other_gate = source.index('run_strict_gate "source-of-truth matrix"')
    assert availability < first_other_gate < source.index('"$PG_PYTHON" scripts/build_final_db.py')
    block = _gate_block(source, "raw DSLD label availability")
    assert "scripts/preflight.py" in block
    assert '--raw-root "$RAW_ROOT"' in block and "--products-dir scripts/products" in block
    # The final comparison reads the exact root that was checked up front.
    assert '--raw-root "$RAW_ROOT"' in _gate_block(source, "raw-to-final line integrity")
    assert "brand_dataset_root()" in source[:availability]


def test_raw_to_final_gate_has_no_skip_path_and_nothing_is_stamped_before_it() -> None:
    source = SCRIPT.read_text()
    assert "set -euo pipefail" in source
    line = source.index('run_strict_gate "raw-to-final line integrity"')
    for later in ("stamp-manifest", "--record-catalog", '"$PG_PYTHON" scripts/promote_release_artifacts.py',
                  "release_catalog_artifact.py"):
        assert line < source.index(later), later
    for label in ("raw DSLD label availability", "raw-to-final line integrity"):
        block = _gate_block(source, label)
        assert "||" not in block and "SKIP" not in block and "if " not in block, block


def test_raw_label_gates_are_never_satisfied_by_a_reused_receipt() -> None:
    import sys
    sys.path.insert(0, str(SCRIPT.parent))
    from audits.run_verification_gate import REUSABLE_RELEASE_GATES
    assert "raw-to-final line integrity" not in REUSABLE_RELEASE_GATES
    assert "raw DSLD label availability" not in REUSABLE_RELEASE_GATES
