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
    assert 'if [[ -z "$RELEASE_CANDIDATE_ROOT" && -d "$FLUTTER_REPO" ]]' in text


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
