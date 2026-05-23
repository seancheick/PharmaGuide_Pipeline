from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_project_pins_python_313():
    assert (REPO_ROOT / ".python-version").read_text().strip().startswith("3.13")


def test_release_shell_scripts_use_shared_python_runtime():
    scripts = [
        REPO_ROOT / "scripts" / "release_full.sh",
        REPO_ROOT / "scripts" / "rebuild_interaction_db.sh",
        REPO_ROOT / "scripts" / "rebuild_dashboard_snapshot.sh",
        REPO_ROOT / "scripts" / "run_fda_sync.sh",
    ]

    for script in scripts:
        text = script.read_text()
        assert "scripts/python_env.sh" in text, f"{script} must source the shared runtime guard"
        assert "python3 " not in text, f"{script} must use $PG_PYTHON, not direct python3"


def test_test_runner_uses_shared_runtime_and_named_profiles():
    runner = REPO_ROOT / "scripts" / "test.sh"
    text = runner.read_text()

    assert "scripts/python_env.sh" in text
    assert '"$PG_PYTHON" -m pytest' in text
    assert "python3 " not in text
    for profile in ("fast", "release", "full", "slow"):
        assert f"{profile})" in text


def test_pytest_suite_auto_marks_heavy_release_and_artifact_tests():
    conftest = (REPO_ROOT / "scripts" / "tests" / "conftest.py").read_text()
    pytest_ini = (REPO_ROOT / "pytest.ini").read_text()

    assert "pytest_collection_modifyitems" in conftest
    for marker in ("slow", "release", "artifact"):
        assert f"pytest.mark.{marker}" in conftest
        assert f"{marker}:" in pytest_ini


def test_release_full_syncs_dist_catalog_back_to_final_db_before_freshness_gate():
    text = (REPO_ROOT / "scripts" / "release_full.sh").read_text()

    assert "sync_final_db_output_catalog_from_dist" in text
    assert text.index("sync_final_db_output_catalog_from_dist") < text.index(
        'run_strict_gate "artifact freshness"'
    )


def test_python_runtime_helper_rejects_pre_313():
    helper = (REPO_ROOT / "scripts" / "python_env.sh").read_text()

    assert "PG_REQUIRED_PYTHON_MINOR=\"${PG_REQUIRED_PYTHON_MINOR:-13}\"" in helper
    assert "/usr/local/bin/python3" in helper
    assert "/opt/homebrew/bin/python3" in helper
    assert "sys.version_info < (major, minor)" in helper
    assert "Xcode/launchd/cron" in helper
