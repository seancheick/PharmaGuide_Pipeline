"""Content-based freshness contract for enrichment reference inputs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_pipeline as pipeline_module
from pipeline_freshness import (
    REFERENCE_FINGERPRINT_KEY,
    enrichment_reference_fingerprint,
    enrichment_reference_freshness_issues,
)
from run_pipeline import PipelineRunner
from stage_manifest import StageManifestError, write_stage_manifest


def test_reference_fingerprint_ignores_mtime_only_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    data_file = repo / "scripts" / "data" / "reference.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text('{"value": 1}\n', encoding="utf-8")

    before = enrichment_reference_fingerprint(repo)
    os.utime(data_file, (data_file.stat().st_atime, data_file.stat().st_mtime + 60))

    assert enrichment_reference_fingerprint(repo) == before


def test_enrich_manifest_records_its_reference_input_fingerprint(
    tmp_path: Path,
) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    output = stage_dir / "enriched_batch_1.json"
    output.write_text("[]\n", encoding="utf-8")
    reference_fingerprint = "a" * 64

    manifest_path = write_stage_manifest(
        stage_dir,
        "enrich",
        [output],
        input_fingerprints={REFERENCE_FINGERPRINT_KEY: reference_fingerprint},
    )

    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["input_fingerprints"] == {
        REFERENCE_FINGERPRINT_KEY: reference_fingerprint,
    }


def test_pipeline_stamps_reference_fingerprint_after_enrichment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = PipelineRunner()
    expected = "b" * 64
    captured: dict = {}

    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)
    monkeypatch.setattr(runner, "_validate_input_dir", lambda *_args: True)
    monkeypatch.setattr(runner, "run_enrich", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pipeline_module,
        "quarantine_stage_outputs",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        pipeline_module,
        "enrichment_reference_fingerprint",
        lambda _repo_root: expected,
        raising=False,
    )

    def capture_manifest(*_args, **kwargs):
        captured.update(kwargs)
        return tmp_path / ".stage_manifest.json"

    monkeypatch.setattr(
        pipeline_module,
        "write_stage_manifest_from_directory",
        capture_manifest,
    )

    result = runner.run_pipeline(
        stages=["enrich"],
        output_prefix=str(tmp_path / "output_Test"),
    )

    assert result["success"] is True
    assert captured["input_fingerprints"] == {
        REFERENCE_FINGERPRINT_KEY: expected,
    }


def test_reference_preflight_ignores_touch_when_content_matches(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    data_file = repo / "scripts" / "data" / "reference.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text('{"value": 1}\n', encoding="utf-8")
    expected = enrichment_reference_fingerprint(repo)

    stage_dir = (
        repo
        / "scripts"
        / "products"
        / "output_Test_enriched"
        / "enriched"
    )
    stage_dir.mkdir(parents=True)
    output = stage_dir / "enriched_batch_1.json"
    output.write_text("[]\n", encoding="utf-8")
    write_stage_manifest(
        stage_dir,
        "enrich",
        [output],
        input_fingerprints={REFERENCE_FINGERPRINT_KEY: expected},
    )

    os.utime(data_file, (data_file.stat().st_atime, output.stat().st_mtime + 60))

    assert enrichment_reference_freshness_issues(repo) == []


def test_reference_preflight_rejects_changed_content(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    data_file = repo / "scripts" / "data" / "reference.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text('{"value": 1}\n', encoding="utf-8")
    expected = enrichment_reference_fingerprint(repo)

    stage_dir = (
        repo
        / "scripts"
        / "products"
        / "output_Test_enriched"
        / "enriched"
    )
    stage_dir.mkdir(parents=True)
    output = stage_dir / "enriched_batch_1.json"
    output.write_text("[]\n", encoding="utf-8")
    write_stage_manifest(
        stage_dir,
        "enrich",
        [output],
        input_fingerprints={REFERENCE_FINGERPRINT_KEY: expected},
    )

    data_file.write_text('{"value": 2}\n', encoding="utf-8")

    issues = enrichment_reference_freshness_issues(repo)
    assert len(issues) == 1
    assert "content mismatch" in issues[0]


def test_manifest_freshness_cli_rejects_stale_enrichment(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    data_file = repo / "scripts" / "data" / "reference.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text('{"value": 1}\n', encoding="utf-8")
    expected = enrichment_reference_fingerprint(repo)

    stage_dir = (
        repo
        / "scripts"
        / "products"
        / "output_Product_Submissions_enriched"
        / "enriched"
    )
    stage_dir.mkdir(parents=True)
    output = stage_dir / "enriched_batch_1.json"
    output.write_text("[]\n", encoding="utf-8")
    manifest = write_stage_manifest(
        stage_dir,
        "enrich",
        [output],
        input_fingerprints={REFERENCE_FINGERPRINT_KEY: expected},
    )

    command = [
        sys.executable,
        str(Path(pipeline_module.__file__).with_name("pipeline_freshness.py")),
        "check-enrichment-manifest",
        "--repo-root",
        str(repo),
        "--manifest",
        str(manifest),
    ]
    current = subprocess.run(command, capture_output=True, text=True)
    assert current.returncode == 0, current.stderr

    data_file.write_text('{"value": 2}\n', encoding="utf-8")
    stale = subprocess.run(command, capture_output=True, text=True)
    assert stale.returncode == 1
    assert "content mismatch" in stale.stderr


def test_release_preflight_uses_reference_content_fingerprints() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "scripts" / "test.sh").read_text(encoding="utf-8")
    start = text.index("release_preflight_staleness_check() {")
    end = text.index("\nrun_release_artifact_gates()", start)
    function = text[start:end]

    assert "enrichment_reference_freshness_issues" in function
    assert "newest_data > newest_enriched" not in function


def test_stage_manifest_rejects_malformed_input_fingerprint(
    tmp_path: Path,
) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    output = stage_dir / "enriched_batch_1.json"
    output.write_text("[]\n", encoding="utf-8")

    with pytest.raises(StageManifestError, match="input fingerprint"):
        write_stage_manifest(
            stage_dir,
            "enrich",
            [output],
            input_fingerprints={REFERENCE_FINGERPRINT_KEY: "not-a-sha256"},
        )


def test_pipeline_rejects_reference_change_during_enrichment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = PipelineRunner()
    before = "a" * 64
    after = "b" * 64
    fingerprints = iter([before, after])
    manifest_written = False

    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)
    monkeypatch.setattr(runner, "_validate_input_dir", lambda *_args: True)
    monkeypatch.setattr(runner, "run_enrich", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pipeline_module,
        "quarantine_stage_outputs",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        pipeline_module,
        "enrichment_reference_fingerprint",
        lambda _repo_root: next(fingerprints),
    )

    def capture_manifest(*_args, **_kwargs):
        nonlocal manifest_written
        manifest_written = True
        return tmp_path / ".stage_manifest.json"

    monkeypatch.setattr(
        pipeline_module,
        "write_stage_manifest_from_directory",
        capture_manifest,
    )

    result = runner.run_pipeline(
        stages=["enrich"],
        output_prefix=str(tmp_path / "output_Test"),
    )

    assert result["success"] is False
    assert result["stages_failed"] == ["enrich"]
    assert manifest_written is False


def test_reference_preflight_reports_malformed_manifest_fail_closed(
    tmp_path: Path,
) -> None:
    import json

    repo = tmp_path / "repo"
    data_file = repo / "scripts" / "data" / "reference.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text('{"value": 1}\n', encoding="utf-8")

    stage_dir = (
        repo
        / "scripts"
        / "products"
        / "output_Test_enriched"
        / "enriched"
    )
    stage_dir.mkdir(parents=True)
    output = stage_dir / "enriched_batch_1.json"
    output.write_text("[]\n", encoding="utf-8")
    manifest_path = write_stage_manifest(stage_dir, "enrich", [output])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["input_fingerprints"] = "corrupt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    issues = enrichment_reference_freshness_issues(repo)

    assert len(issues) == 1
    assert "malformed" in issues[0]
