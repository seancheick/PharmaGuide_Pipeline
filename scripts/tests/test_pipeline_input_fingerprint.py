"""Content-based freshness contract for stage inputs: reference data and code."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_pipeline as pipeline_module
from pipeline_freshness import (
    CODE_FINGERPRINT_KEY,
    REFERENCE_FINGERPRINT_KEY,
    STAGES,
    reference_data_fingerprint,
    stage_code_files,
    stage_code_fingerprint,
    stage_freshness_issues,
    stage_input_fingerprints,
)
from run_pipeline import PipelineRunner
from stage_manifest import StageManifestError, write_stage_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fake_repo(tmp_path: Path) -> Path:
    """A repo with one reference-data file and a stub script for every stage."""
    repo = tmp_path / "repo"
    data_file = repo / "scripts" / "data" / "reference.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text('{"value": 1}\n', encoding="utf-8")
    for spec in STAGES.values():
        (repo / "scripts" / spec["entry"]).write_text("VALUE = 1\n", encoding="utf-8")
    return repo


def _stage_output(repo: Path, stage: str, *, stamp: bool = True) -> Path:
    """One output file for a stage, with a manifest of the current inputs."""
    relative = {
        "clean": ("output_Test", "cleaned", "cleaned_batch_1.json"),
        "enrich": ("output_Test_enriched", "enriched", "enriched_batch_1.json"),
        "score": ("output_Test_scored", "scored", "scored_batch_1.json"),
    }[stage]
    output = repo.joinpath("scripts", "products", *relative)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("[]\n", encoding="utf-8")
    write_stage_manifest(
        output.parent,
        stage,
        [output],
        input_fingerprints=stage_input_fingerprints(repo, stage) if stamp else None,
    )
    return output


def test_reference_fingerprint_ignores_mtime_only_changes(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    data_file = repo / "scripts" / "data" / "reference.json"

    before = reference_data_fingerprint(repo)
    os.utime(data_file, (data_file.stat().st_atime, data_file.stat().st_mtime + 60))

    assert reference_data_fingerprint(repo) == before


def test_code_fingerprint_ignores_docstrings_comments_and_layout(
    tmp_path: Path,
) -> None:
    repo = _fake_repo(tmp_path)
    entry = repo / "scripts" / STAGES["enrich"]["entry"]
    helper = repo / "scripts" / "helper.py"
    entry.write_text("from helper import dose\n", encoding="utf-8")
    helper.write_text(
        'def dose():\n    """Old words."""\n    return 1\n', encoding="utf-8"
    )
    before = stage_code_fingerprint(repo, "enrich")

    helper.write_text(
        '"""A module docstring."""\n\n\ndef dose():  # a comment\n'
        '    """New words."""\n\n    return 1\n',
        encoding="utf-8",
    )
    assert stage_code_fingerprint(repo, "enrich") == before

    helper.write_text("def dose():\n    return 2\n", encoding="utf-8")
    assert stage_code_fingerprint(repo, "enrich") != before


def test_code_fingerprint_follows_imports_and_skips_unrelated_modules(
    tmp_path: Path,
) -> None:
    repo = _fake_repo(tmp_path)
    scripts = repo / "scripts"
    (scripts / STAGES["score"]["entry"]).write_text(
        "def main():\n    from pkg.mod import value\n    return value\n",
        encoding="utf-8",
    )
    (scripts / "pkg").mkdir()
    (scripts / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (scripts / "pkg" / "mod.py").write_text(
        "from . import sub\nvalue = sub.VALUE\n", encoding="utf-8"
    )
    (scripts / "pkg" / "sub.py").write_text("VALUE = 1\n", encoding="utf-8")
    (scripts / "unrelated.py").write_text("VALUE = 1\n", encoding="utf-8")

    files = {path.relative_to(scripts).as_posix() for path in stage_code_files(repo, "score")}
    assert {"pkg/__init__.py", "pkg/mod.py", "pkg/sub.py"} <= files
    assert "unrelated.py" not in files

    before = stage_code_fingerprint(repo, "score")
    (scripts / "unrelated.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert stage_code_fingerprint(repo, "score") == before
    (scripts / "pkg" / "sub.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert stage_code_fingerprint(repo, "score") != before


def test_stage_config_is_part_of_the_stage_code(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    config = repo / "scripts" / "scoring_v4" / "config" / "quality_score.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"cap": 13}\n', encoding="utf-8")
    before = stage_code_fingerprint(repo, "score")

    config.write_text('{"cap": 15}\n', encoding="utf-8")

    assert stage_code_fingerprint(repo, "score") != before


def test_missing_stage_script_fails_closed(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    (repo / "scripts" / STAGES["clean"]["entry"]).unlink()

    with pytest.raises(ValueError, match="clean stage script is missing"):
        stage_code_fingerprint(repo, "clean")


def test_real_stage_code_covers_each_stage_owner() -> None:
    files = {
        stage: {
            path.relative_to(REPO_ROOT / "scripts").as_posix()
            for path in stage_code_files(REPO_ROOT, stage)
        }
        for stage in STAGES
    }

    assert {"batch_processor.py", "enhanced_normalizer.py", "config/cleaning_config.json"} <= files["clean"]
    assert {"enrich_supplements_v3.py", "unit_converter.py", "config/enrichment_config.json"} <= files["enrich"]
    assert {"score_supplements_v4.py", "scoring_v4/config/quality_score.json"} <= files["score"]
    assert not any(path.startswith("tests/") for stage_files in files.values() for path in stage_files)


def test_enrich_manifest_records_its_input_fingerprints(tmp_path: Path) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    output = stage_dir / "enriched_batch_1.json"
    output.write_text("[]\n", encoding="utf-8")
    inputs = {REFERENCE_FINGERPRINT_KEY: "a" * 64, CODE_FINGERPRINT_KEY: "c" * 64}

    manifest_path = write_stage_manifest(
        stage_dir,
        "enrich",
        [output],
        input_fingerprints=inputs,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["input_fingerprints"] == inputs


@pytest.mark.parametrize("stage", ["enrich", "score"])
def test_pipeline_stamps_input_fingerprints_after_each_stage(
    tmp_path: Path,
    monkeypatch,
    stage: str,
) -> None:
    runner = PipelineRunner()
    expected = {REFERENCE_FINGERPRINT_KEY: "b" * 64, CODE_FINGERPRINT_KEY: "c" * 64}
    captured: dict = {}

    monkeypatch.setattr(runner, "_validate_data_dir", lambda: True)
    monkeypatch.setattr(runner, "_validate_input_dir", lambda *_args: True)
    monkeypatch.setattr(runner, f"run_{stage}", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runner, "_load_products_for_gates", lambda *_a, **_k: ([], None))
    monkeypatch.setattr(runner, "run_enrichment_contract_gate", lambda *_a, **_k: (True, {}))
    monkeypatch.setattr(
        pipeline_module,
        "quarantine_stage_outputs",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        pipeline_module,
        "stage_input_fingerprints",
        lambda _repo_root, stage_name: dict(expected, stage=stage_name),
    )

    def capture_manifest(*args, **kwargs):
        captured.update(kwargs, stage=args[1])
        return tmp_path / ".stage_manifest.json"

    monkeypatch.setattr(
        pipeline_module,
        "write_stage_manifest_from_directory",
        capture_manifest,
    )

    result = runner.run_pipeline(
        stages=[stage],
        output_prefix=str(tmp_path / "output_Test"),
        skip_coverage_gate=True,
    )

    assert result["success"] is True
    assert captured["stage"] == stage
    assert captured["input_fingerprints"] == dict(expected, stage=stage)


def test_custom_stage_scripts_leave_the_code_unproven() -> None:
    runner = PipelineRunner()
    runner.config["scripts"] = dict(runner.config["scripts"], score="other_scorer.py")

    inputs = runner._stage_inputs("score")

    assert REFERENCE_FINGERPRINT_KEY in inputs
    assert CODE_FINGERPRINT_KEY not in inputs


def test_preflight_ignores_touch_when_content_matches(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    data_file = repo / "scripts" / "data" / "reference.json"
    output = _stage_output(repo, "enrich")

    os.utime(data_file, (data_file.stat().st_atime, output.stat().st_mtime + 60))

    assert stage_freshness_issues(repo) == []


def test_preflight_rejects_changed_reference_content(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    _stage_output(repo, "enrich")

    (repo / "scripts" / "data" / "reference.json").write_text(
        '{"value": 2}\n', encoding="utf-8"
    )

    issues = stage_freshness_issues(repo)
    assert len(issues) == 1
    assert issues[0].startswith("enrich: ")
    assert "reference_data fingerprint content mismatch" in issues[0]


def test_preflight_rejects_output_built_by_other_code(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    for stage in STAGES:
        _stage_output(repo, stage)
    assert stage_freshness_issues(repo) == []

    (repo / "scripts" / STAGES["enrich"]["entry"]).write_text(
        "VALUE = 2\n", encoding="utf-8"
    )

    issues = stage_freshness_issues(repo)
    assert len(issues) == 1
    assert issues[0].startswith("enrich: ")
    assert "stage code fingerprint content mismatch" in issues[0]


def test_preflight_rejects_output_without_a_code_fingerprint(tmp_path: Path) -> None:
    """A corpus stamped before code fingerprints existed proves nothing."""
    repo = _fake_repo(tmp_path)
    output = _stage_output(repo, "score", stamp=False)
    write_stage_manifest(
        output.parent,
        "score",
        [output],
        input_fingerprints={REFERENCE_FINGERPRINT_KEY: reference_data_fingerprint(repo)},
    )

    issues = stage_freshness_issues(repo)
    assert len(issues) == 1
    assert "stage code fingerprint missing" in issues[0]


def test_manifest_freshness_cli_rejects_any_stale_stage(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    command = [
        sys.executable,
        str(Path(pipeline_module.__file__).with_name("pipeline_freshness.py")),
        "check-stage-manifests",
        "--repo-root",
        str(repo),
    ]
    for stage in STAGES:
        manifest = _stage_output(repo, stage).parent / ".stage_manifest.json"
        command += [f"--{stage}", str(manifest)]
    current = subprocess.run(command, capture_output=True, text=True)
    assert current.returncode == 0, current.stderr

    (repo / "scripts" / STAGES["score"]["entry"]).write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    code_changed = subprocess.run(command, capture_output=True, text=True)
    assert code_changed.returncode == 1
    assert "stage code fingerprint content mismatch" in code_changed.stderr

    (repo / "scripts" / "data" / "reference.json").write_text(
        '{"value": 2}\n', encoding="utf-8"
    )
    stale = subprocess.run(command, capture_output=True, text=True)
    assert stale.returncode == 1
    assert "reference_data fingerprint content mismatch" in stale.stderr


def test_release_preflight_uses_stage_content_fingerprints() -> None:
    text = (REPO_ROOT / "scripts" / "test.sh").read_text(encoding="utf-8")
    start = text.index("release_preflight_staleness_check() {")
    end = text.index("\nrun_release_artifact_gates()", start)
    function = text[start:end]

    assert "stage_freshness_issues" in function
    assert "SKIP_RELEASE=1 bash batch_run_all_datasets.sh --stages" in function
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


def test_pipeline_rejects_input_change_during_enrichment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = PipelineRunner()
    before = {REFERENCE_FINGERPRINT_KEY: "a" * 64, CODE_FINGERPRINT_KEY: "c" * 64}
    after = {REFERENCE_FINGERPRINT_KEY: "a" * 64, CODE_FINGERPRINT_KEY: "d" * 64}
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
        "stage_input_fingerprints",
        lambda _repo_root, _stage: dict(next(fingerprints)),
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


def test_preflight_reports_malformed_manifest_fail_closed(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path)
    output = _stage_output(repo, "enrich", stamp=False)
    manifest_path = output.parent / ".stage_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["input_fingerprints"] = "corrupt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    issues = stage_freshness_issues(repo)

    assert len(issues) == 1
    assert "malformed" in issues[0]
