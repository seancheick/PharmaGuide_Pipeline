import json
import re
from pathlib import Path

import pytest


@pytest.mark.parametrize('branch,require_branch,expected', [('main', 1, 0), ('', 1, 1), ('', 0, 0)])
def test_release_base_rejects_detached_flutter_before_expensive_work(branch, require_branch, expected):
    import subprocess
    source = SCRIPT.read_text()
    start = source.index('require_release_base() {')
    end = source.index('\n# Manufacturer penalties', start)
    harness = '''
err() { echo "$*" >&2; }
git() {
  case "$*" in
    *"branch --show-current"*) printf '%s' "$TEST_BRANCH" ;;
    *"rev-parse"*) echo aabbccdd ;;
    *) return 0 ;;
  esac
}
'''
    result = subprocess.run(['bash', '-c', harness + source[start:end] +
                             f'\nrequire_release_base /fake/repo {require_branch}\n'],
                            capture_output=True, text=True,
                            env={'TEST_BRANCH': branch})
    assert result.returncode == expected, result.stdout + result.stderr
    if expected:
        assert 'detached' in result.stderr.lower()


SCRIPT = Path(__file__).resolve().parents[1] / "release_full.sh"
INTERACTION_SCRIPT = Path(__file__).resolve().parents[1] / "rebuild_interaction_db.sh"
INTERACTION_VERSION_CONFIG = (
    Path(__file__).resolve().parents[1] / "config" / "interaction_db_release.json"
)


@pytest.mark.parametrize('accepted', [True, False])
def test_producer_compatibility_uses_importer_before_any_candidate_exists(tmp_path, accepted):
    import subprocess
    import sys
    import shlex
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (scripts / 'build_final_db.py').write_text('EXPORT_SCHEMA_VERSION = "2.5.0"\n')
    (scripts / 'build_interaction_db.py').write_text('SCHEMA_VERSION = "4.0.0"\n')
    app = tmp_path / 'app/scripts'
    app.mkdir(parents=True)
    importer = app / 'import_catalog_artifact.sh'
    importer.write_text('#!/bin/bash\n[[ "$*" == "--check-compatibility 2.5.0 4.0.0" ]] || exit 9\nexit ' + str(0 if accepted else 1))
    importer.chmod(0o755)
    source = SCRIPT.read_text()
    function = source.split('require_producer_compatibility() {', 1)[1].split('\n}', 1)[0]
    harness = f'''REPO_ROOT={shlex.quote(str(tmp_path))}
FLUTTER_REPO={shlex.quote(str(app.parent))}
PG_PYTHON={shlex.quote(sys.executable)}
err() {{ echo "$*" >&2; }}
require_producer_compatibility() {{{function}
}}
require_producer_compatibility
'''
    result = subprocess.run(['bash', '-c', harness], capture_output=True, text=True)
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr
    assert not (tmp_path / 'dist').exists()


def test_compatibility_precedes_preflight_exit_and_any_release_step():
    source = SCRIPT.read_text()
    call = source.index('require_producer_compatibility || exit 1')
    assert call < source.index('if (( PREFLIGHT_ONLY == 1 ))')
    assert call < source.index('run_strict_gate "source-of-truth matrix"')


def test_compatibility_only_mode_precedes_git_and_publication_checks():
    source = SCRIPT.read_text()
    assert '--compatibility-only)' in source
    call = source.index('if (( COMPATIBILITY_ONLY == 1 )); then')
    assert call < source.index('require_release_base "$REPO_ROOT"')
    assert call < source.index('scripts/sync_to_supabase.py" --preflight-only')


def test_release_full_uses_only_gated_snapshot_for_catalog_mutation() -> None:
    source = SCRIPT.read_text()

    assert source.count("bash scripts/rebuild_dashboard_snapshot.sh") == 1
    assert '"$PG_PYTHON" scripts/build_all_final_dbs.py' not in source
    assert '"$PG_PYTHON" scripts/release_catalog_artifact.py' not in source


def test_release_image_probe_shares_extractor_eligibility() -> None:
    source = SCRIPT.read_text().split("step3_needs_run()", 1)[1].split("if (( SKIP_PRODUCT_IMAGES", 1)[0]
    assert "from extract_product_images import needs_image_extraction" in source
    assert "SELECT COUNT(*)" not in source
    assert ')" || return 0' in source  # probe errors must not silently skip work


def test_release_full_enters_the_global_lock_before_any_release_gate() -> None:
    source = SCRIPT.read_text()

    wrapper = 'scripts/run_with_release_lock.py'
    assert wrapper in source
    assert source.index(wrapper) < source.index(
        'run_strict_gate "source-of-truth matrix"'
    )


def test_interaction_import_fallback_uses_gated_catalog_path() -> None:
    source = INTERACTION_SCRIPT.read_text()

    assert "bash scripts/rebuild_dashboard_snapshot.sh" in source
    assert '"$PG_PYTHON" scripts/release_catalog_artifact.py' not in source


def test_interaction_rebuild_default_comes_from_tracked_release_config() -> None:
    config = json.loads(INTERACTION_VERSION_CONFIG.read_text())
    source = INTERACTION_SCRIPT.read_text()
    release_source = SCRIPT.read_text()

    # The contract is that the rebuild reads the tracked config, not that the
    # version never moves: a curated rule change must be able to bump it.
    assert re.fullmatch(r"\d+\.\d+\.\d+", config["interaction_db_version"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", config["build_time_utc"])
    assert 'INTERACTION_VERSION_CONFIG="$SCRIPT_DIR/config/interaction_db_release.json"' in source
    assert "interaction_db_version" in source
    assert "build_time_utc" in source
    assert '--build-time "$INTERACTION_BUILD_TIME"' in source
    assert (
        '--restage-build-current' in release_source
        and 'scripts/config/interaction_db_release.json' in
        SCRIPT.with_name('release_interaction_artifact.py').read_text()
    )
    assert 'INTERACTION_VERSION="1.0.2"' not in source


def test_interaction_rebuild_regenerates_the_derived_suppai_feed() -> None:
    source = INTERACTION_SCRIPT.read_text()
    release_source = SCRIPT.read_text()

    assert 'SUPPAI_DIR="${PHARMAGUIDE_SUPPAI_DIR:-' in source
    assert '--suppai-dir "$SUPPAI_DIR"' in source
    assert '--build-time "$INTERACTION_BUILD_TIME"' in source
    assert 'if [[ ! -f "$OUTPUT_DIR/research_pairs.json" ]]' not in source
    import release_interaction_artifact as interaction_owner
    assert '--restage-build-current' in release_source
    assert 'scripts/data/ingredient_quality_map.json' in interaction_owner.INTERACTION_REQUIRED_INPUTS
    assert set(interaction_owner.SUPPAI_INPUT_NAMES) == {
        'cui_metadata.json', 'interaction_id_dict.json', 'meta.json',
        'paper_metadata.json', 'sentence_dict.json',
    }


def test_release_moves_the_app_hydration_pin_with_the_bundle() -> None:
    source = SCRIPT.read_text()
    publish = '--publish-flutter-pin "$FLUTTER_REPO"'
    verify = 'bash "$FLUTTER_REPO/tool/fetch_interaction_db.sh"'
    pin = "tool/interaction_db.release.json"

    # Published after every preflight gate, before anything reaches Supabase.
    assert source.index('run_strict_gate "Flutter import preflight"') < source.index(publish)
    assert source.index(publish) < source.index("# Step 5: Sync to Supabase")
    # The app's own hydration verifier checks pin, manifest and DB before the commit.
    assert source.index('run_strict_gate "Flutter bundle parity"') < source.index(verify)
    add_line = next(l for l in source.splitlines() if 'git -C "$FLUTTER_REPO" add' in l)
    status_line = next(l for l in source.splitlines() if "status --porcelain -- assets/db" in l)
    assert source.index(verify) < source.index(add_line)
    assert pin in add_line
    assert pin in status_line


def test_release_preflight_only_local_run_never_reaches_artifact_gates():
    import os
    import subprocess
    result = subprocess.run(
        ["bash", str(SCRIPT), "--preflight-only", "--skip-supabase", "--skip-flutter"],
        capture_output=True, text=True, env={**os.environ}, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Release prerequisites passed" in result.stdout
    assert "Step 1/8" not in result.stdout


def test_release_checks_flutter_main_with_existing_release_base_owner():
    source = SCRIPT.read_text()
    publishing = source.split('if (( SKIP_FLUTTER == 0 ||', 1)[1].split('START_TS=', 1)[0]
    assert 'require_release_base "$FLUTTER_REPO" "$(( SKIP_SUPABASE == 0 && SUPABASE_DRY_RUN == 0 ))" || exit 1' in publishing
    assert publishing.index('require_release_base "$FLUTTER_REPO"') < publishing.index('PREFLIGHT_ONLY == 1')


@pytest.mark.parametrize("prepared,stale,expected", [
    (True, False, "preserved"), (True, True, "refused"),
    (False, False, "fetched"),
])
@pytest.mark.parametrize("force", [False, True])
def test_release_prepared_inputs_preserve_verified_submission_set(tmp_path, prepared, stale, expected, force):
    import os
    import shlex
    import subprocess

    source = SCRIPT.read_text()
    start = source.index("submission_labels_exist() {")
    stage_zero = source[start:source.index("# Step 1:", start)]
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "label.json").write_text("{}")
    manifests = [tmp_path / name for name in ["clean.json", "enrich.json", "score.json"]]
    for manifest in manifests:
        manifest.write_text("{}")
    os.utime(raw / "label.json", (1, 1))
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/bin/bash\n"
        'if [[ "$*" == *check-stage-manifests* ]]; then exit ' + str(int(stale)) + '; fi\n'
        'echo "$*" >> "$RELEASE_PROBE_CALLS"\n'
    )
    fake_python.chmod(0o755)
    calls = tmp_path / "calls"
    variables = {
        "PG_PYTHON": str(fake_python), "REPO_ROOT": str(tmp_path),
        "SUBMISSION_OUTPUT_DIR": str(raw), "SUBMISSION_PIPELINE_PREFIX": str(tmp_path / "out"),
        "SUBMISSION_CLEAN_MANIFEST": str(manifests[0]),
        "SUBMISSION_ENRICH_MANIFEST": str(manifests[1]),
        "SUBMISSION_SCORE_MANIFEST": str(manifests[2]),
    }
    harness = "set -e\nFORCE=" + str(int(force)) + "\nSKIP_SUPABASE=0\nSUPABASE_DRY_RUN=0\nPREPARED_INPUTS=" + str(int(prepared)) + "\n"
    harness += "\n".join(f"{k}={shlex.quote(v)}" for k, v in variables.items()) + "\n"
    harness += 'info(){ :; }; ok(){ :; }; skip(){ echo "$*"; }; err(){ echo "$*"; };\n'
    result = subprocess.run(["bash", "-c", harness + stage_zero], text=True, capture_output=True,
                            env={**os.environ, "RELEASE_PROBE_CALLS": str(calls)}, timeout=15)
    recorded = calls.read_text() if calls.exists() else ""
    if expected == "refused":
        assert result.returncode != 0
        assert "prepared" in (result.stdout + result.stderr).lower()
        assert "--fetch" not in recorded
        assert "run_pipeline.py" not in recorded
    elif expected == "preserved":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--fetch" not in recorded
        assert "run_pipeline.py" not in recorded
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--fetch" in recorded


def test_release_cli_accepts_prepared_inputs_in_read_only_preflight():
    import os
    import subprocess
    result = subprocess.run(
        ["bash", str(SCRIPT), "--preflight-only", "--skip-supabase", "--skip-flutter", "--prepared-inputs"],
        capture_output=True, text=True, env={**os.environ}, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Release prerequisites passed" in result.stdout
    assert "Step 1/8" not in result.stdout


def test_release_defaults_to_prepared_intake_with_explicit_refresh_opt_in():
    source = SCRIPT.read_text()
    defaults = source[source.index('FLUTTER_REPO='):source.index('# CLI parsing')]
    assert 'PREPARED_INPUTS=1' in defaults
    assert '--refresh-submissions)' in source
    assert '--refresh-submissions) PREPARED_INPUTS=0' in source


@pytest.mark.parametrize('force', [0, 1])
def test_stale_catalog_is_assembled_only_once_even_when_forced(tmp_path, force):
    import subprocess
    source = SCRIPT.read_text()
    start = source.index('step1_needs_run()')
    end = source.index('# Run even when assembly/staging was skipped.', start)
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (scripts / 'rebuild_dashboard_snapshot.sh').write_text('echo built >> builds\n')
    fake = tmp_path / 'python'
    fake.write_text('#!/bin/bash\nexit 1\n')  # receipt not current
    fake.chmod(0o755)
    header = f'''set -e
FORCE={force}
SCORING_SNAPSHOT_GATE_RAN=0
PG_PYTHON='{fake}'
CATALOG_STATE_SCRIPT=unused
DIST_CATALOG=absent
FINAL_CATALOG=absent
info() {{ :; }}
ok() {{ :; }}
skip() {{ :; }}
run_strict_gate() {{
  local label="$1"; shift
  if [[ "$label" == "catalog assembly" ]]; then "$@"; fi
}}
'''
    result = subprocess.run(['bash', '-c', header + source[start:end]],
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'builds').read_text().splitlines() == ['built']


@pytest.mark.parametrize("compatibility_fails,skip_flutter", [(False, False), (True, False), (False, True)])
def test_batch_runner_stops_before_processing_when_canary_preflight_fails(tmp_path, compatibility_fails, skip_flutter):
    import os
    import shutil
    import subprocess
    import sys

    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    repo = SCRIPT.parents[1]
    shutil.copyfile(repo / "batch_run_all_datasets.sh", root / "batch_run_all_datasets.sh")
    shutil.copyfile(repo / "scripts/python_env.sh", scripts / "python_env.sh")
    raw_root = tmp_path / "raw"
    (raw_root / "Brand").mkdir(parents=True)
    calls = tmp_path / "calls.txt"
    calls.write_text("")
    # Isolate the existing earlier compatibility boundary; never run the real
    # release script, importer, pipeline or a cloud request from this harness.
    compatibility = scripts / "release_full.sh"
    compatibility.write_text(
        '#!/bin/bash\n'
        '[[ "$1" == "--compatibility-only" ]] || exit 91\n'
        'echo compatibility >> "$TEST_CALLS"\n'
        'exit "$TEST_COMPATIBILITY_EXIT"\n')
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
        f"with Path({str(calls)!r}).open('a') as f:f.write(' '.join(sys.argv[1:])+'\\n')\n"
        "sys.exit(7 if '--prepare' in sys.argv else 0)\n")
    fake_python.chmod(0o755)
    env = dict(os.environ, PG_PYTHON=sys.executable, PYTHON=str(fake_python),
               TEST_CALLS=str(calls), TEST_COMPATIBILITY_EXIT=str(int(compatibility_fails)))
    command = ["bash", str(root / "batch_run_all_datasets.sh"),
               "--root", str(raw_root), "--pipeline-only", "--pre-check"]
    if skip_flutter:
        command.append("--skip-flutter")
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0, result.stdout + result.stderr
    invocations = [call for call in calls.read_text().splitlines()
                   if not call.startswith('pipeline_freshness.py batch-source-fingerprint ')]
    preparation = [call for call in invocations if "--prepare" in call and "--raw-root" in call]
    if compatibility_fails:
        assert invocations == ["compatibility"]
        assert "phone consumer compatibility failed" in result.stdout
    else:
        assert len(preparation) == 1
        assert "aggregate preparation failed" in result.stdout
        quick = [call for call in invocations if "--quick" in call]
        assert len(quick) == 1
        assert invocations == ([*quick, *preparation] if skip_flutter else ["compatibility", *quick, *preparation])
    assert not any("run_pipeline.py" in call or "release_full.sh" in call for call in invocations)


@pytest.mark.parametrize("pre_check,quick_fails", [(False, False), (True, False), (False, True)])
def test_batch_preparation_is_opt_in_but_quick_checks_remain(tmp_path, pre_check, quick_fails):
    import os
    import shutil
    import subprocess
    import sys

    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(SCRIPT.parents[1] / "batch_run_all_datasets.sh", root / "batch_run_all_datasets.sh")
    shutil.copyfile(SCRIPT.parent / "python_env.sh", scripts / "python_env.sh")
    raw = tmp_path / "raw"
    (raw / "Brand").mkdir(parents=True)
    calls = tmp_path / "calls"
    fake = tmp_path / "python"
    fake.write_text(f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
                    f"with Path({str(calls)!r}).open('a') as f: f.write(' '.join(sys.argv[1:])+'\\n')\n"
                    f"sys.exit(8 if {quick_fails!r} and '--quick' in sys.argv else 0)\n")
    fake.chmod(0o755)
    command = ["bash", str(root / "batch_run_all_datasets.sh"), "--root", str(raw),
               "--pipeline-only", "--skip-flutter"]
    if pre_check:
        command.append("--pre-check")
    result = subprocess.run(command, env=dict(os.environ, PG_PYTHON=sys.executable, PYTHON=str(fake)),
                            capture_output=True, text=True, timeout=20)
    invocations = [call for call in calls.read_text().splitlines()
                   if not call.startswith('pipeline_freshness.py batch-source-fingerprint ')]
    quick = [call for call in invocations if '--quick' in call]
    prep = [call for call in invocations if '--prepare' in call]
    pipeline = [call for call in invocations if 'run_pipeline.py' in call]
    assert len(quick) == 1
    if quick_fails:
        assert result.returncode != 0
        assert not prep and not pipeline
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(prep) == int(pre_check)
        assert len(pipeline) == 1
        assert '--stages clean,enrich,score --strict-release-gates' in pipeline[0]
        assert invocations.index(quick[0]) < invocations.index(pipeline[0])
        if prep:
            assert invocations.index(quick[0]) < invocations.index(prep[0]) < invocations.index(pipeline[0])
    assert not any('rebuild_dashboard_snapshot.sh' in call or 'release_full.sh' in call for call in invocations)


@pytest.mark.parametrize("pre_check", [False, True])
def test_batch_precheck_flag_preserves_full_release_path(tmp_path, pre_check):
    import os
    import shutil
    import subprocess
    import sys

    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(SCRIPT.parents[1] / "batch_run_all_datasets.sh", root / "batch_run_all_datasets.sh")
    shutil.copyfile(SCRIPT.parent / "python_env.sh", scripts / "python_env.sh")
    raw = tmp_path / "raw"
    (raw / "Brand").mkdir(parents=True)
    calls = tmp_path / "calls"
    fake = tmp_path / "python"
    fake.write_text(f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
                    f"with Path({str(calls)!r}).open('a') as f: f.write(' '.join(sys.argv[1:])+'\\n')\n")
    fake.chmod(0o755)
    # Only dispatch is exercised: no real importer, pipeline, snapshot, cloud
    # operation or Flutter mutation is available inside this synthetic repo.
    release = scripts / "release_full.sh"
    release.write_text('#!/bin/bash\n'
                       'if [[ "$1" == "--preflight-only" ]]; then\n'
                       '  echo prerequisites >> "$TEST_CALLS"\n'
                       'else\n'
                       '  echo "release $*" >> "$TEST_CALLS"\n'
                       'fi\n')
    release.chmod(0o755)
    snapshot = scripts / "rebuild_dashboard_snapshot.sh"
    snapshot.write_text('#!/bin/bash\necho snapshot >> "$TEST_CALLS"\n')
    snapshot.chmod(0o755)
    env = dict(os.environ, PG_PYTHON=sys.executable, PYTHON=str(fake), TEST_CALLS=str(calls),
               SKIP_SNAPSHOT="0", SKIP_RELEASE="0")
    command = ["bash", str(root / "batch_run_all_datasets.sh"), "--root", str(raw)]
    if pre_check:
        command.append("--pre-check")
    result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    invocations = [call for call in calls.read_text().splitlines()
                   if not call.startswith('pipeline_freshness.py batch-source-fingerprint ')]
    assert invocations[0] == 'prerequisites'
    assert 'product_submission_import.py --fetch' in invocations[1]
    assert 'preflight.py --quick' in invocations[2]
    prepare = [call for call in invocations if '--prepare' in call.split()]
    assert len(prepare) == int(pre_check)
    pipeline = next(call for call in invocations if 'run_pipeline.py' in call)
    assert '--stages clean,enrich,score --strict-release-gates' in pipeline
    if prepare:
        assert invocations.index(prepare[0]) < invocations.index(pipeline)
    assert invocations[-2:] == ['snapshot', 'release --prepared-inputs']


@pytest.mark.parametrize("commit_outcome", ["unchanged", "success", "failure"])
def test_release_finishes_bundle_without_running_storage_maintenance(tmp_path, commit_outcome):
    import shlex
    import subprocess

    source = SCRIPT.read_text()
    block = source[source.index('# Commit the Flutter bundle'):source.index('# A submission becomes')]
    calls = tmp_path / 'maintenance_calls'
    python = tmp_path / 'python'
    python.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(calls)) + '\nexit 17\n')
    python.chmod(0o755)
    harness = f'''SKIP_FLUTTER=0
SKIP_SUPABASE=0
SUPABASE_DRY_RUN=0
FLUTTER_REPO={shlex.quote(str(tmp_path))}
KEEP_VERSIONS=2
PG_PYTHON={shlex.quote(str(python))}
CATALOG_VERSION=test
INTERACTION_VERSION=test
info() {{ printf '%s\\n' "$*"; }}
warn() {{ printf '%s\\n' "$*"; }}
err() {{ printf '%s\\n' "$*"; }}
skip() {{ printf '%s\\n' "$*"; }}
ok() {{ printf '%s\\n' "$*"; }}
git() {{
  case "$*" in
    *"rev-parse --is-inside-work-tree"*) echo true ;;
    *"branch --show-current"*) echo main ;;
    *"status --porcelain"*) {":" if commit_outcome == "unchanged" else "echo modified"} ;;
    *" add "*) return 0 ;;
    *" commit "*) return {1 if commit_outcome == "failure" else 0} ;;
    *) return 9 ;;
  esac
}}
'''
    result = subprocess.run(['bash', '-c', harness + block + '\necho RELEASE_FINISHED\n'], capture_output=True, text=True)
    assert result.returncode == (1 if commit_outcome == 'failure' else 0), result.stdout + result.stderr
    if commit_outcome == 'failure':
        assert 'RELEASE_FINISHED' not in result.stdout
        assert 'commit failed' in result.stdout
        assert not calls.exists()
        return
    assert not calls.exists(), 'release must not wait on optional storage listing/deletion'
    assert 'Version cleanup: DEFERRED' in result.stdout
    assert 'Orphan cleanup: DEFERRED' in result.stdout
    assert 'cleanup_old_versions.py' in result.stdout
    assert 'RELEASE_FINISHED' in result.stdout
    if commit_outcome == 'success':
        assert 'Flutter bundle committed locally' in result.stdout
    else:
        assert 'already committed' in result.stdout


def test_release_python_progress_is_visible_through_a_pipe():
    import os
    import shlex
    import subprocess
    import sys

    # Exercise the real release initialization, stopping before runtime selection,
    # locks, configuration, network or filesystem mutation.
    prefix = SCRIPT.read_text().split('SCRIPT_DIR=', 1)[0]
    env = dict(os.environ)
    env.pop('PYTHONUNBUFFERED', None)
    command = shlex.quote(sys.executable) + " -c 'import sys; print(sys.stdout.write_through)'"
    result = subprocess.run(['bash', '-c', prefix + command], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'True', 'piped release progress must not sit in Python buffers'

@pytest.mark.parametrize('skip_flutter', [0, 1])
def test_reference_data_skip_flutter_never_writes_app(tmp_path, skip_flutter):
    import subprocess
    source = SCRIPT.read_text()
    block = source[source.index('# Pipeline reference files are canonical.'):source.index('# A fresh per-brand rebuild')]
    harness = f'''SKIP_FLUTTER={skip_flutter}
PG_PYTHON=python
FLUTTER_REPO=/app
run_strict_gate() {{ printf '%s\\n' "$*"; }}
skip() {{ :; }}
'''
    result = subprocess.run(['bash', '-c', harness + block], capture_output=True, text=True)
    assert result.returncode == 0
    calls = [line for line in result.stdout.splitlines() if 'sync_flutter_reference_data.py' in line]
    assert calls
    if skip_flutter:
        assert all('--check' in line for line in calls)
    else:
        assert len(calls) == 2

def test_manifest_field_reader_handles_quoted_custom_app_path(tmp_path):
    import shlex
    import subprocess
    import sys
    manifest = tmp_path / "Sean's app.json"
    manifest.write_text(json.dumps({'checksum_sha256': 'verified'}))
    source = SCRIPT.read_text()
    function = source[source.index('json_field() {'):source.index('\nfile_sha256()')]
    result = subprocess.run(['bash', '-c',
        'PG_PYTHON=' + shlex.quote(sys.executable) + '\n' + function +
        '\njson_field ' + shlex.quote(str(manifest)) + ' checksum_sha256'],
        capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == 'verified'
