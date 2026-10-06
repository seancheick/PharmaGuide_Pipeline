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


def test_test_profiles_use_one_manifest_and_classify_generated_artifacts():
    manifest = REPO_ROOT / "scripts" / "test_profiles.py"
    assert manifest.exists(), "test profile ownership must live in one Python manifest"

    runner_text = (REPO_ROOT / "scripts" / "test.sh").read_text()
    conftest_text = (REPO_ROOT / "scripts" / "tests" / "conftest.py").read_text()
    assert "test_profiles.py" in runner_text
    assert "from test_profiles import" in conftest_text

    from test_profiles import ARTIFACT_TEST_FILES

    assert {
        "test_scoring_snapshot_v1.py",
        "test_unii_cache.py",
        "test_dsld_278523_folate_parent_total_2026_05_25.py",
        "test_unii_exoneration_allowlist.py",
    } <= ARTIFACT_TEST_FILES


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


def test_raw_snapshot_preflight_detects_drift_while_stored_outputs_match(tmp_path, monkeypatch, capsys):
    import json
    import shutil
    import sys
    from scripts.tests import freeze_contract_snapshots as freezer

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    shutil.copyfile(REPO_ROOT / "scripts/tests/fixtures/plant_part_204571_raw.json",
                    raw_root / "204571.json")
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    frozen = {"dsld_id": "204571", "quality_score_v4_100": 62.5,
              "quality_score_status": "scored", "product_safety_status": "no_known_catalog_concern"}
    snapshot = fixtures / "204571.json"
    snapshot.write_text(json.dumps(frozen))
    manifest = fixtures / "_manifest.json"
    manifest.write_text(json.dumps({"fixture_schema": {"frozen_fields": list(frozen)},
        "products": [{"dsld_id": 204571, "brand_source": "Garden_of_life", "label": "Adrenal"}]}))
    products = tmp_path / "products"
    stored = products / "output_Garden_of_life_scored/scored"
    stored.mkdir(parents=True)
    (stored / "old.json").write_text(json.dumps([frozen]))
    monkeypatch.setattr(freezer, "MANIFEST", manifest)
    monkeypatch.setattr(freezer, "FIXTURE_DIR", fixtures)
    monkeypatch.setattr(freezer, "PRODUCTS_ROOT", products)
    monkeypatch.setattr(sys, "argv", ["freeze_contract_snapshots.py", "--check"])
    assert freezer.main() == 0
    monkeypatch.setattr(sys, "argv", ["freeze_contract_snapshots.py", "--check", "--raw-root", str(raw_root)])
    assert freezer.main() == 1
    output = capsys.readouterr().out
    assert "62.5 -> 63.5" in output
    assert json.loads(snapshot.read_text()) == frozen
    assert json.loads((stored / "old.json").read_text()) == [frozen]


def test_batch_runner_stops_before_processing_when_canary_preflight_fails(tmp_path):
    import os
    import shutil
    import subprocess
    import sys

    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / "batch_run_all_datasets.sh", root / "batch_run_all_datasets.sh")
    shutil.copyfile(REPO_ROOT / "scripts/python_env.sh", scripts / "python_env.sh")
    raw_root = tmp_path / "raw"
    (raw_root / "Brand").mkdir(parents=True)
    calls = tmp_path / "calls.txt"
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
        f"with Path({str(calls)!r}).open('a') as f:f.write(' '.join(sys.argv[1:])+'\\n')\n"
        "sys.exit(7 if '--prepare' in sys.argv else 0)\n")
    fake_python.chmod(0o755)
    env = dict(os.environ, PG_PYTHON=sys.executable, PYTHON=str(fake_python))
    result = subprocess.run(["bash", str(root / "batch_run_all_datasets.sh"),
        "--root", str(raw_root), "--pipeline-only"], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    invocations = calls.read_text().splitlines()
    assert any("--prepare" in call and "--raw-root" in call for call in invocations)
    assert not any("run_pipeline.py" in call or "release_full.sh" in call for call in invocations)


def test_raw_snapshot_preflight_refuses_missing_ambiguous_and_wrong_identity(tmp_path, monkeypatch, capsys):
    import json
    import sys
    from scripts.tests import freeze_contract_snapshots as freezer

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    frozen = {"dsld_id": "204571", "quality_score_v4_100": 62.5}
    snapshot = fixtures / "204571.json"
    snapshot.write_text(json.dumps(frozen))
    manifest = fixtures / "_manifest.json"
    manifest.write_text(json.dumps({"fixture_schema": {"frozen_fields": list(frozen)},
        "products": [{"dsld_id": 204571, "brand_source": "Garden_of_life"}]}))
    monkeypatch.setattr(freezer, "MANIFEST", manifest)
    monkeypatch.setattr(freezer, "FIXTURE_DIR", fixtures)
    monkeypatch.setattr(sys, "argv", ["freeze_contract_snapshots.py", "--check", "--raw-root", str(raw_root)])
    assert freezer.main() == 1
    assert "found 0" in capsys.readouterr().out
    for child in ["first", "second"]:
        (raw_root / child).mkdir()
        (raw_root / child / "204571.json").write_text(json.dumps({"id": 999}))
    assert freezer.main() == 1
    assert "found 2" in capsys.readouterr().out
    (raw_root / "second/204571.json").unlink()
    assert freezer.main() == 1
    assert "raw label identity does not match" in capsys.readouterr().out
    assert json.loads(snapshot.read_text()) == frozen


def test_preparation_explicit_nodes_still_use_suite_lock_and_inventory_gates():
    text = (REPO_ROOT / 'scripts/test.sh').read_text()
    assert 'preparation) lock_mode=exclusive' in text
    assert 'preparation-gates)' in text
    assert 'release_gate source "$PG_PYTHON" scripts/iqm_form_evidence.py audit' in text
    assert 'release_gate live "$PG_PYTHON" scripts/iqm_form_evidence.py verify-live' in text
