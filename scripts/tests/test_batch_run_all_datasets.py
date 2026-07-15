import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "batch_run_all_datasets.sh"


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
        f"#!/bin/bash\ntouch '{release_marker}'\n",
        encoding="utf-8",
    )
    snapshot.chmod(snapshot.stat().st_mode | stat.S_IXUSR)
    release.chmod(release.stat().st_mode | stat.S_IXUSR)

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
