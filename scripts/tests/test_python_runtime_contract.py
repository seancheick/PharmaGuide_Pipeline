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


def test_python_runtime_helper_rejects_pre_313():
    helper = (REPO_ROOT / "scripts" / "python_env.sh").read_text()

    assert "PG_REQUIRED_PYTHON_MINOR=\"${PG_REQUIRED_PYTHON_MINOR:-13}\"" in helper
    assert "sys.version_info < (major, minor)" in helper
    assert "Xcode/launchd/cron" in helper
