import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "batch_run_all_datasets.sh"
PYTHON_ENV_PATH = REPO_ROOT / "scripts" / "python_env.sh"


def test_full_pipeline_only_checks_phone_consumer_before_preparation(tmp_path):
    dataset = tmp_path / 'raw/Test'
    dataset.mkdir(parents=True)
    (dataset / 'one.json').write_text('{}')
    _install_batch_dependencies(tmp_path)
    release = tmp_path / 'scripts/release_full.sh'
    release.write_text('#!/bin/bash\necho compatibility-probe\nexit 17\n')
    runner = tmp_path / 'batch_run_all_datasets.sh'
    runner.write_text(SCRIPT_PATH.read_text())
    result = subprocess.run(['bash', str(runner), '--root', str(dataset.parent), '--pipeline-only'],
                            env={**os.environ}, text=True, capture_output=True)
    assert result.returncode != 0
    assert 'compatibility-probe' in result.stdout
    assert 'aggregate-preparation-reached' not in result.stdout


def _install_batch_dependencies(tmp_path):
    """Install the runtime selector and a successful preflight in the fake repo.

    These tests isolate downstream batch orchestration. The real raw preflight
    and its early-failure behavior have their own owner/consumer regressions.
    The fake entry point validates the caller's arguments rather than bypassing
    the production guard or silently skipping a missing dependency.
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    if not (scripts_dir / 'pipeline_freshness.py').exists():
        (scripts_dir / 'pipeline_freshness.py').write_text("print('stable-source')\n")
    (scripts_dir / "python_env.sh").write_text(
        PYTHON_ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    if not (scripts_dir / "release_full.sh").exists():
        (scripts_dir / "release_full.sh").write_text("#!/bin/bash\nexit 0\n")
    if not (scripts_dir / "product_submission_import.py").exists():
        (scripts_dir / "product_submission_import.py").write_text(
            "import sys\nassert sys.argv[1:3] == ['--fetch', '--output-dir']\n"
            "assert len(sys.argv) == 4\nprint('approved-intake-reached')\n"
        )
    (scripts_dir / "tests").mkdir(exist_ok=True)
    (scripts_dir / "preflight.py").write_text(
        "import sys\n"
        "if sys.argv[1] == '--quick':\n"
        "    assert sys.argv[2] == '--raw-root' and len(sys.argv) >= 4\n"
        "    print('essential-preflight-reached')\n"
        "elif sys.argv[1] == '--release-readiness':\n"
        "    assert sys.argv[2] == '--raw-root' and len(sys.argv) == 4\n"
        "    print('assessment-readiness-reached')\n"
        "else:\n"
        "    assert sys.argv[1:3] == ['--prepare', '--raw-root']\n"
        "    assert len(sys.argv) == 4\n"
        "    print('aggregate-preparation-reached')\n",
        encoding="utf-8",
    )


def test_batch_runner_defaults_to_local_non_icloud_dataset_root(tmp_path):
    fake_home = tmp_path / "home"
    dataset_root = (
        fake_home
        / "Downloads"
        / "PharmaGuide_Datasets"
        / "staging"
        / "brands"
    )
    (dataset_root / "ExampleBrand").mkdir(parents=True)

    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "products" / "reports").mkdir(parents=True)
    (scripts_dir / "run_pipeline.py").write_text(
        "import sys\n"
        "print('local-root-runner-reached')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )

    _install_batch_dependencies(tmp_path)

    copied_script = tmp_path / "batch_run_all_datasets.sh"
    copied_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    copied_script.chmod(copied_script.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(copied_script), "--pipeline-only"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(fake_home),
            "PYTHONUNBUFFERED": "1",
        },
    )

    combined_output = result.stdout + result.stderr
    assert str(dataset_root) in combined_output
    assert "local-root-runner-reached" in combined_output
    assert combined_output.index("essential-preflight-reached") < combined_output.index("local-root-runner-reached")
    assert "aggregate-preparation-reached" not in combined_output
    assert result.returncode == 1, combined_output


def test_batch_runner_reports_local_dataset_hydration_in_progress(tmp_path):
    fake_home = tmp_path / "home"
    hydrating_root = (
        fake_home
        / "Downloads"
        / "PharmaGuide_Datasets"
        / ".hydrating"
        / "brands"
        / "ExampleBrand"
    )
    hydrating_root.mkdir(parents=True)
    (hydrating_root / "1.json").write_text("{}", encoding="utf-8")
    (tmp_path / "scripts").mkdir()

    _install_batch_dependencies(tmp_path)

    copied_script = tmp_path / "batch_run_all_datasets.sh"
    copied_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    copied_script.chmod(copied_script.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(copied_script), "--pipeline-only"],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(fake_home)},
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Local dataset hydration is still in progress" in combined_output
    assert "1 JSON file(s) copied so far" in combined_output


def test_batch_runner_propagates_run_pipeline_failures(tmp_path):
    dataset_root = tmp_path / "datasets"
    dataset_dir = dataset_root / "ExampleBrand"
    dataset_dir.mkdir(parents=True)

    scripts_dir = tmp_path / "scripts"
    products_reports = scripts_dir / "products" / "reports"
    products_reports.mkdir(parents=True)

    fake_runner = scripts_dir / "run_pipeline.py"
    fake_runner.write_text(
        "import sys\n"
        "print('simulated pipeline failure')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )

    _install_batch_dependencies(tmp_path)

    copied_script = tmp_path / "batch_run_all_datasets.sh"
    copied_script.write_text(
        SCRIPT_PATH.read_text(encoding="utf-8").replace(
            'SCRIPTS_DIR="/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts"',
            f'SCRIPTS_DIR="{scripts_dir}"',
        ),
        encoding="utf-8",
    )
    copied_script.chmod(copied_script.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(copied_script), "--root", str(dataset_root)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1, combined_output
    assert "FAILED: ExampleBrand" in combined_output
    assert "Some datasets failed processing." in combined_output


def test_batch_runner_propagates_snapshot_failure_and_skips_release(tmp_path):
    dataset_root = tmp_path / "datasets"
    (dataset_root / "ExampleBrand").mkdir(parents=True)

    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "products" / "reports").mkdir(parents=True)

    (scripts_dir / "run_pipeline.py").write_text(
        "print('simulated pipeline success')\n",
        encoding="utf-8",
    )
    snapshot = scripts_dir / "rebuild_dashboard_snapshot.sh"
    snapshot.write_text(
        "#!/bin/bash\necho 'simulated snapshot failure'\nexit 3\n",
        encoding="utf-8",
    )
    release_marker = tmp_path / "release-ran"
    release = scripts_dir / "release_full.sh"
    release.write_text(
        f"#!/bin/bash\n[[ \"$1\" == --preflight-only ]] && exit 0\ntouch '{release_marker}'\n",
        encoding="utf-8",
    )
    snapshot.chmod(snapshot.stat().st_mode | stat.S_IXUSR)
    release.chmod(release.stat().st_mode | stat.S_IXUSR)

    _install_batch_dependencies(tmp_path)

    copied_script = tmp_path / "batch_run_all_datasets.sh"
    copied_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    copied_script.chmod(copied_script.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(copied_script), "--root", str(dataset_root)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1, combined_output
    assert "Snapshot rebuild failed" in combined_output
    assert not release_marker.exists()


def _batch_with_stale_submissions(tmp_path, *args):
    dataset_root = tmp_path / "datasets"
    (dataset_root / "ExampleBrand").mkdir(parents=True)

    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "products" / "reports").mkdir(parents=True)
    submission_dir = tmp_path / "manual_labels" / "product_submissions"
    submission_dir.mkdir(parents=True)
    (submission_dir / "approved.json").write_text("{}\n", encoding="utf-8")

    call_log = tmp_path / "pipeline-calls.txt"
    (scripts_dir / "run_pipeline.py").write_text(
        "import os, sys\n"
        "with open(os.environ['PIPELINE_CALL_LOG'], 'a', encoding='utf-8') as f:\n"
        "    f.write(' '.join(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    (scripts_dir / "pipeline_freshness.py").write_text(
        "import sys\n"
        "if sys.argv[1] == 'batch-source-fingerprint': print('stable-source'); raise SystemExit(0)\n"
        "assert sys.argv[1] == 'check-stage-manifests'\n"
        "print('content mismatch', file=sys.stderr)\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    snapshot = scripts_dir / "rebuild_dashboard_snapshot.sh"
    snapshot.write_text("#!/bin/bash\necho snapshot-ok\n", encoding="utf-8")
    snapshot.chmod(snapshot.stat().st_mode | stat.S_IXUSR)

    _install_batch_dependencies(tmp_path)

    copied_script = tmp_path / "batch_run_all_datasets.sh"
    copied_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    copied_script.chmod(copied_script.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(copied_script), "--root", str(dataset_root), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "PIPELINE_CALL_LOG": str(call_log), "PYTHONUNBUFFERED": "1"},
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []
    return calls, submission_dir


def test_pipeline_only_full_run_refreshes_stale_product_submissions(tmp_path):
    """A pipeline-only run is followed by a manual snapshot, whose freshness gate
    reads the submission outputs too (2026-09-29: it stopped on submissions built
    at the previous head)."""
    calls, submission_dir = _batch_with_stale_submissions(tmp_path, "--pipeline-only")
    assert len(calls) == 2, calls
    assert f"--raw-dir {submission_dir}" in calls[1]


def test_targeted_pipeline_run_leaves_product_submissions_alone(tmp_path):
    calls, _ = _batch_with_stale_submissions(tmp_path, "--targets", "ExampleBrand")
    assert len(calls) == 1, calls


def test_full_batch_refreshes_stale_product_submissions_before_snapshot(tmp_path):
    dataset_root = tmp_path / "datasets"
    (dataset_root / "ExampleBrand").mkdir(parents=True)

    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "products" / "reports").mkdir(parents=True)
    submission_dir = tmp_path / "manual_labels" / "product_submissions"
    submission_dir.mkdir(parents=True)
    (submission_dir / "approved.json").write_text("{}\n", encoding="utf-8")

    call_log = tmp_path / "pipeline-calls.txt"
    (scripts_dir / "run_pipeline.py").write_text(
        "import os, sys\n"
        "with open(os.environ['PIPELINE_CALL_LOG'], 'a', encoding='utf-8') as f:\n"
        "    f.write(' '.join(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    (scripts_dir / "pipeline_freshness.py").write_text(
        "import sys\n"
        "if sys.argv[1] == 'batch-source-fingerprint': print('stable-source'); raise SystemExit(0)\n"
        "assert sys.argv[1] == 'check-stage-manifests'\n"
        "print('content mismatch', file=sys.stderr)\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    snapshot = scripts_dir / "rebuild_dashboard_snapshot.sh"
    snapshot.write_text("#!/bin/bash\necho snapshot-ok\n", encoding="utf-8")
    snapshot.chmod(snapshot.stat().st_mode | stat.S_IXUSR)

    _install_batch_dependencies(tmp_path)

    copied_script = tmp_path / "batch_run_all_datasets.sh"
    copied_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    copied_script.chmod(copied_script.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        [
            "bash",
            str(copied_script),
            "--root",
            str(dataset_root),
            "--skip-release",
        ],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PIPELINE_CALL_LOG": str(call_log),
            "PYTHONUNBUFFERED": "1",
        },
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 2, calls
    assert "output_ExampleBrand" in calls[0]
    assert f"--raw-dir {submission_dir}" in calls[1]
    assert "--output-prefix products/output_Product_Submissions" in calls[1]
    assert "--stages clean,enrich,score" in calls[1]
    assert combined_output.index("Product Submissions") < combined_output.index(
        "snapshot-ok"
    )


def test_batch_full_run_refuses_release_prerequisites_before_preparation_or_brands(tmp_path):
    dataset_root = tmp_path / "data"
    (dataset_root / "ExampleBrand").mkdir(parents=True)
    _install_batch_dependencies(tmp_path)
    scripts = tmp_path / "scripts"
    (scripts / "release_full.sh").write_text(
        "#!/bin/bash\n[[ \"$1\" == --preflight-only ]] || exit 90\necho release-prerequisite-refused\nexit 42\n"
    )
    (scripts / "run_pipeline.py").write_text("print('brand-must-not-run')\n")
    runner = tmp_path / "batch_run_all_datasets.sh"
    runner.write_text(SCRIPT_PATH.read_text())
    result = subprocess.run(["bash", str(runner)], capture_output=True, text=True,
                            env={**os.environ, "PHARMAGUIDE_DATASET_ROOT": str(dataset_root)})
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "release-prerequisite-refused" in output
    assert "aggregate-preparation-reached" not in output
    assert "brand-must-not-run" not in output


@pytest.mark.parametrize('intake_fails', [False, True])
def test_default_batch_intake_precedes_validation_and_reaches_flutter_commit(tmp_path, intake_fails):
    data = tmp_path / 'data'
    (data / 'ExampleBrand').mkdir(parents=True)
    _install_batch_dependencies(tmp_path)
    scripts = tmp_path / 'scripts'
    events = tmp_path / 'events'
    event_code = f"from pathlib import Path\np=Path({str(events)!r})\n"
    submissions = tmp_path / 'manual_labels/product_submissions'
    (scripts / 'product_submission_import.py').write_text(event_code +
        "import sys\nassert sys.argv[1:3] == ['--fetch', '--output-dir']\n"
        "with p.open('a') as out: out.write('intake\\n')\n" +
        ("raise SystemExit(4)\n" if intake_fails else
         "raw=Path(sys.argv[3]);raw.mkdir(parents=True,exist_ok=True)\n"
         "(raw/'approved.json').write_text('{}')\n"))
    (scripts / 'preflight.py').write_text(event_code +
        f"assert Path({str(submissions / 'approved.json')!r}).exists(), 'intake must precede preparation'\n"
        "import sys\nkind='readiness' if '--release-readiness' in sys.argv else 'preparation'\n"
        "with p.open('a') as out: out.write(kind+'\\n')\n")
    (scripts / 'run_pipeline.py').write_text(event_code +
        "import sys\nkind='submissions' if 'products/output_Product_Submissions' in sys.argv else 'brand'\n"
        "with p.open('a') as out: out.write(kind+'\\n')\n")
    (scripts / 'pipeline_freshness.py').write_text(
        "import sys\n"
        "if sys.argv[1] == 'batch-source-fingerprint': print('stable-source'); raise SystemExit(0)\n"
        "assert '--raw-inputs' in sys.argv\nraise SystemExit(1)\n")
    snapshot = scripts / 'rebuild_dashboard_snapshot.sh'
    snapshot.write_text(f"#!/bin/bash\nprintf 'snapshot\\n' >> '{events}'\n")
    snapshot.chmod(0o755)
    (scripts / 'release_full.sh').write_text(f'''#!/bin/bash
if [[ "$1" == --preflight-only ]]; then
  printf 'prerequisites\\n' >> '{events}'
  exit 0
fi
[[ " $* " == *" --prepared-inputs "* ]] || exit 90
printf 'supabase\\nflutter-import\\nflutter-commit\\n' >> '{events}'
''')
    (scripts / 'release_full.sh').chmod(0o755)
    batch = tmp_path / 'batch_run_all_datasets.sh'
    batch.write_text(SCRIPT_PATH.read_text())
    result = subprocess.run(['bash', str(batch)], capture_output=True, text=True,
                            env={**os.environ, 'PHARMAGUIDE_DATASET_ROOT': str(data)})
    actual = events.read_text().splitlines()
    if intake_fails:
        assert result.returncode != 0
        assert actual == ['prerequisites', 'intake']
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert actual == ['prerequisites', 'intake', 'preparation', 'readiness', 'brand',
                          'submissions', 'snapshot', 'supabase', 'flutter-import', 'flutter-commit']


# --- Raw DSLD labels are checked before Clean (ADR-0005 raw-to-final gate) ---

def _raw_label_batch(tmp_path, *, real_preflight, brands=("ExampleBrand",), with_json=True):
    dataset_root = tmp_path / "datasets"
    for brand in brands:
        (dataset_root / brand).mkdir(parents=True)
        if with_json:
            (dataset_root / brand / "1.json").write_text("{}", encoding="utf-8")
    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "products" / "reports").mkdir(parents=True)
    (scripts_dir / "run_pipeline.py").write_text(
        "print('clean-reached')\n", encoding="utf-8")
    _install_batch_dependencies(tmp_path)
    if real_preflight:
        # The production preflight owner, run as itself (its own data dir).
        (scripts_dir / "preflight.py").write_text(
            "import runpy, sys\n"
            f"sys.argv[0] = {str(REPO_ROOT / 'scripts/preflight.py')!r}\n"
            f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r})\n"
            "runpy.run_path(sys.argv[0], run_name='__main__')\n",
            encoding="utf-8")
    copied = tmp_path / "batch_run_all_datasets.sh"
    copied.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return dataset_root, copied


def test_batch_runner_refuses_a_dataset_without_raw_labels_before_clean(tmp_path):
    dataset_root, script = _raw_label_batch(tmp_path, real_preflight=True, with_json=False)
    result = subprocess.run(["bash", str(script), "--root", str(dataset_root), "--pipeline-only",
                             "--skip-flutter"], capture_output=True, text=True, timeout=300)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"raw DSLD dataset has no label JSON: {dataset_root / 'ExampleBrand'}" in combined
    assert "clean-reached" not in combined


def test_batch_runner_passes_raw_root_and_selected_datasets_to_preflight(tmp_path):
    dataset_root, script = _raw_label_batch(tmp_path, real_preflight=True, brands=("Olly", "Thorne"))
    result = subprocess.run(["bash", str(script), "--root", str(dataset_root), "--targets", "Olly"],
                            capture_output=True, text=True, timeout=300)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert f"[OK] {dataset_root}" in combined
    assert combined.index(f"[OK] {dataset_root}") < combined.index("clean-reached")


def test_batch_runner_refuses_a_target_with_no_dataset_folder(tmp_path):
    dataset_root, script = _raw_label_batch(tmp_path, real_preflight=False, brands=("Olly",))
    result = subprocess.run(["bash", str(script), "--root", str(dataset_root), "--targets", "Olly,Thorne"],
                            capture_output=True, text=True, timeout=60)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"no dataset folder under {dataset_root} matches target 'Thorne'" in combined
    assert "clean-reached" not in combined and "essential-preflight-reached" not in combined


def test_batch_runner_checks_catalog_raw_labels_when_a_snapshot_will_run(tmp_path):
    # A release run audits every assembled brand against this root; a delta or
    # forms root without them would fail only after the whole corpus run.
    dataset_root, script = _raw_label_batch(tmp_path, real_preflight=True, brands=("Olly",))
    (tmp_path / "scripts/products/output_Thorne_enriched/enriched").mkdir(parents=True)
    result = subprocess.run(["bash", str(script), "--root", str(dataset_root), "--targets", "Olly",
                             "--release", "--skip-supabase", "--skip-flutter"],
                            capture_output=True, text=True, timeout=300)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"raw DSLD dataset missing: {dataset_root / 'Thorne'}" in combined
    assert "clean-reached" not in combined


@pytest.mark.parametrize("targets", ["Olly,", ",Olly", "Olly, ,Thorne", ","])
def test_batch_runner_refuses_an_empty_target_instead_of_running_every_brand(tmp_path, targets):
    # An empty entry is a substring of every folder name, so it would select all brands.
    dataset_root, script = _raw_label_batch(tmp_path, real_preflight=False, brands=("Olly", "Thorne"))
    result = subprocess.run(["bash", str(script), "--root", str(dataset_root), "--targets", targets],
                            capture_output=True, text=True, timeout=60)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"--targets {targets!r} contains an empty entry" in combined
    assert "clean-reached" not in combined and "essential-preflight-reached" not in combined


def test_known_assessment_blocker_stops_before_brand_processing(tmp_path):
    dataset = tmp_path / 'raw/Test'
    dataset.mkdir(parents=True)
    (dataset / 'one.json').write_text('{}')
    _install_batch_dependencies(tmp_path)
    preflight = tmp_path / 'scripts/preflight.py'
    preflight.write_text(preflight.read_text().replace("print('assessment-readiness-reached')", "print('assessment-readiness-reached'); sys.exit(1)"))
    (tmp_path / 'scripts/run_pipeline.py').write_text("raise AssertionError('must not run corpus')")
    runner = tmp_path / 'batch_run_all_datasets.sh'
    runner.write_text(SCRIPT_PATH.read_text())
    result = subprocess.run(['bash', str(runner), '--root', str(dataset.parent)],
                            env={**os.environ}, text=True, capture_output=True)
    assert result.returncode == 1
    assert 'current assessments block publication before corpus work' in result.stdout
    assert 'must not run corpus' not in result.stderr


@pytest.mark.parametrize('targeted', [False, True])
def test_resume_prints_all_plans_before_running_any_brand(tmp_path, targeted):
    raw = tmp_path / 'raw'
    for brand in ('A', 'B'):
        (raw / brand).mkdir(parents=True)
        (raw / brand / 'one.json').write_text('{}')
    _install_batch_dependencies(tmp_path)
    (tmp_path / 'scripts/run_pipeline.py').write_text(
        "import sys\n"
        "print(('PLAN ' if '--resume-plan' in sys.argv else 'RUN ') + sys.argv[sys.argv.index('--raw-dir')+1])\n"
        "assert '--resume-plan' in sys.argv or '--resume' in sys.argv\n")
    submissions = tmp_path / 'manual_labels/product_submissions'
    submissions.mkdir(parents=True)
    (submissions / 'one.json').write_text('{}')
    runner = tmp_path / 'batch_run_all_datasets.sh'
    runner.write_text(SCRIPT_PATH.read_text())
    extra = ['--targets', 'A'] if targeted else []
    result = subprocess.run(['bash', str(runner), '--root', str(raw), '--pipeline-only', '--resume', *extra],
                            text=True, capture_output=True, env={**os.environ})
    assert result.returncode == 0, result.stdout + result.stderr
    lines = [line for line in result.stdout.splitlines() if line.startswith(('PLAN ', 'RUN '))]
    expected = ['PLAN', 'RUN'] if targeted else ['PLAN'] * 3 + ['RUN'] * 3
    assert [line.split()[0] for line in lines] == expected


def test_batch_stops_after_source_drift_before_next_brand(tmp_path):
    raw = tmp_path / 'raw'
    for brand in ('A', 'B'):
        (raw / brand).mkdir(parents=True)
        (raw / brand / 'one.json').write_text('{}')
    _install_batch_dependencies(tmp_path)
    (tmp_path / 'scripts/pipeline_freshness.py').write_text(
        "from pathlib import Path\nprint(Path('changed').exists())\n")
    (tmp_path / 'scripts/run_pipeline.py').write_text(
        "from pathlib import Path\nprint('brand-ran')\nPath('changed').touch()\n")
    runner = tmp_path / 'batch_run_all_datasets.sh'
    runner.write_text(SCRIPT_PATH.read_text())
    result = subprocess.run(['bash', str(runner), '--root', str(raw), '--pipeline-only'],
                            text=True, capture_output=True, env={**os.environ})
    assert result.returncode != 0
    assert result.stdout.count('brand-ran') == 1
    assert 'source changed' in result.stdout.lower()
