"""Candidate-artifact support for the pinned release test profile."""

from pathlib import Path
import importlib

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "test.sh"
STAMP_PARITY = REPO_ROOT / "scripts" / "tests" / "test_catalog_stamp_parity_release.py"
SOURCE_OF_TRUTH = REPO_ROOT / "scripts" / "tests" / "test_source_of_truth_contract.py"


def _runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_release_profile_accepts_preserved_candidate_root() -> None:
    text = _runner_text()

    assert 'RELEASE_CANDIDATE_ROOT="${PG_RELEASE_CANDIDATE_ROOT:-}"' in text
    assert 'release_artifact_dirs' in text
    assert '"$RELEASE_CANDIDATE_ROOT/dist"' in text
    assert '"$RELEASE_CANDIDATE_ROOT/final_db_output"' in text


def test_candidate_release_uses_candidate_freshness_without_flutter_parity() -> None:
    text = _runner_text()

    assert 'release_preflight_candidate_check' in text
    assert '--skip-interaction-inputs' in text
    assert '( -z "$RELEASE_CANDIDATE_ROOT" && -d "$FLUTTER_REPO" )' in text
    assert '"${PG_GATE_MODE:-}" == "inventory"' in text


def test_candidate_root_must_be_absolute_and_complete() -> None:
    text = _runner_text()

    assert 'PG_RELEASE_CANDIDATE_ROOT must be an absolute path' in text
    assert 'candidate dist/final_db_output pair is incomplete' in text


def test_catalog_stamp_parity_uses_the_shared_release_artifact_resolver() -> None:
    text = STAMP_PARITY.read_text(encoding="utf-8")

    assert "from scripts.release_artifact_paths import catalog_dist_dir" in text
    assert "DIST = catalog_dist_dir()" in text
    assert 'DIST = ROOT / "scripts" / "dist"' not in text


def test_interaction_parity_uses_the_shared_release_artifact_resolver() -> None:
    text = SOURCE_OF_TRUTH.read_text(encoding="utf-8")

    assert "from scripts.release_artifact_paths import catalog_dist_dir" in text
    assert "dist = catalog_dist_dir()" in text


@pytest.mark.parametrize("module_name,test_name", [
    ("test_dashboard_smoke", "test_all_dashboard_views_smoke_render"),
    ("test_dashboard_smoke", "test_inspector_drilldown_renders_v4_for_real_product"),
    ("test_graceful_degradation", "test_inspector_drill_down_real_product"),
])
def test_real_dashboard_probes_read_candidate_build(
    monkeypatch, tmp_path, dashboard_app, module_name, test_name
):
    monkeypatch.setenv("PG_RELEASE_CANDIDATE_ROOT", str(tmp_path))

    class CandidateSelected(Exception):
        pass

    def capture_config(config):
        assert config.build_root == tmp_path / "final_db_output"
        raise CandidateSelected

    monkeypatch.setattr(dashboard_app, "load_dashboard_data", capture_config)
    module = importlib.import_module(f"scripts.tests.{module_name}")
    with pytest.raises(CandidateSelected):
        getattr(module, test_name)(dashboard_app)


@pytest.mark.parametrize("module_name,function_name", [
    ("test_form_sensitive_nutrient_gate", "_resolve_detail_blobs_dir"),
    ("test_label_fidelity_contract", "_find_blob_dir"),
])
def test_blob_probes_use_candidate_build_without_live_fallback(
    monkeypatch, tmp_path, module_name, function_name
):
    monkeypatch.setenv("PG_RELEASE_CANDIDATE_ROOT", str(tmp_path))
    module = importlib.import_module(f"scripts.tests.{module_name}")
    resolver = getattr(module, function_name)
    # An absent candidate must not silently pass by reading an older live build.
    assert resolver() is None
    blobs = tmp_path / "final_db_output" / "detail_blobs"
    blobs.mkdir(parents=True)
    (blobs / "candidate.json").write_text('{"candidate_probe": true}')
    assert resolver() == blobs
    dist = tmp_path / "dist" / "detail_blobs"
    dist.mkdir(parents=True)
    (dist / "candidate.json").write_text('{"candidate_probe": true}')
    assert resolver() == dist


def test_ul_blob_probe_reads_selected_candidate(monkeypatch, tmp_path):
    monkeypatch.setenv("PG_RELEASE_CANDIDATE_ROOT", str(tmp_path))
    blobs = tmp_path / "dist" / "detail_blobs"
    blobs.mkdir(parents=True)
    (blobs / "candidate.json").write_text('{"candidate_probe": true}')
    module = importlib.import_module(
        "scripts.tests.test_e1_5_x_4_ul_fallback_and_status"
    )
    assert list(module._iter_blobs()) == [{"candidate_probe": True}]


def test_release_gate_execution_cannot_be_disabled_by_inherited_inventory_environment(tmp_path):
    import os
    import subprocess
    text = _runner_text()
    functions = text[text.index('release_gate() {'):text.index('\nfast_test_files()')]
    calls = tmp_path / 'calls'
    fake_python = tmp_path / 'python'
    fake_python.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$GATE_CALL_LOG"\n')
    fake_python.chmod(0o755)
    script = functions + '\nPG_PYTHON="$FAKE_GATE_PYTHON"\nRELEASE_DIST_DIR=dist\nRELEASE_FINAL_DB_DIR=final\nRELEASE_CANDIDATE_ROOT=""\nFLUTTER_REPO=missing\nrun_release_artifact_gates\n'
    result = subprocess.run(['bash', '-c', script], env=dict(os.environ,
        PG_GATE_MODE='inventory', SKIP_LIVE_IDENTITY_GATES='1', GATE_CALL_LOG=str(calls),
        FAKE_GATE_PYTHON=str(fake_python)), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    commands = calls.read_text().splitlines()
    assert 'scripts/iqm_form_evidence.py audit' in commands
    assert 'scripts/coverage_gate_functional_roles.py' in commands
    assert not any(command.startswith('-c ') for command in commands)
