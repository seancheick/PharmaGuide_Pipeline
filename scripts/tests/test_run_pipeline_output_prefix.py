"""Regression tests for run_pipeline.py path resolution.

Bug: when --output-prefix begins with "scripts/" and the user invokes from
repo root, the subprocess (CWD=scripts/) re-resolves the relative path,
producing scripts/scripts/products/... artifacts.

Verified 2026-05-24 by Pure Encapsulations rerun. Workaround was rsync.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_pipeline as pipeline_module  # noqa: E402
from run_pipeline import PipelineRunner  # noqa: E402


def _capture_runner(monkeypatch):
    """Return (runner, captured_args_list) with subprocess + validators stubbed."""
    captured: list[tuple[str, list[str]]] = []

    def fake_run_script(self, script_name, args, dry_run=False):
        captured.append((script_name, list(args)))
        return True

    monkeypatch.setattr(PipelineRunner, "_run_script", fake_run_script)
    monkeypatch.setattr(PipelineRunner, "_validate_data_dir", lambda self: True)
    monkeypatch.setattr(
        PipelineRunner, "_validate_input_dir", lambda self, d, s: True
    )
    monkeypatch.setattr(
        pipeline_module, "quarantine_stage_outputs", lambda *_args: []
    )
    monkeypatch.setattr(
        pipeline_module,
        "write_stage_manifest_from_directory",
        lambda *_args, **_kwargs: Path(".stage_manifest.json"),
    )

    return PipelineRunner(), captured


def _resolve_against_scripts_cwd(arg: str, scripts_dir: Path) -> Path:
    """Simulate how a subprocess with CWD=scripts/ would resolve the arg."""
    p = Path(arg)
    if p.is_absolute():
        return p
    return (scripts_dir / p).resolve()


def _get_arg(args: list[str], flag: str) -> str | None:
    if flag not in args:
        return None
    return args[args.index(flag) + 1]


def test_output_prefix_with_scripts_prefix_does_not_double(monkeypatch):
    """Repro of the Pure Encapsulations bug.

    --output-prefix=scripts/products/output_TestBrand from repo root
    must not produce scripts/scripts/products/... when the subprocess
    resolves the path against its CWD (scripts/).
    """
    runner, captured = _capture_runner(monkeypatch)

    runner.run_pipeline(
        stages=["clean", "enrich"],  # skip score => skip coverage gate
        raw_dir="/tmp/test_raw_does_not_need_to_exist",
        output_prefix="scripts/products/output_TestBrand",
        dry_run=False,
    )

    assert captured, "no subprocess invocations were captured"

    for script_name, args in captured:
        for flag in ("--input-dir", "--output-dir"):
            value = _get_arg(args, flag)
            if value is None:
                continue
            resolved = _resolve_against_scripts_cwd(value, runner.script_dir)
            assert "scripts/scripts" not in str(resolved), (
                f"{script_name} {flag}={value!r} resolves to doubled path "
                f"{resolved} when subprocess CWD is scripts/"
            )


def test_output_prefix_absolute_path_is_preserved(monkeypatch, tmp_path):
    """Absolute --output-prefix paths are passed through unchanged."""
    runner, captured = _capture_runner(monkeypatch)

    abs_prefix = str(tmp_path / "output_AbsBrand")
    runner.run_pipeline(
        stages=["clean"],
        raw_dir=str(tmp_path / "raw"),
        output_prefix=abs_prefix,
        dry_run=False,
    )

    assert captured
    args = captured[0][1]
    output_dir = _get_arg(args, "--output-dir")
    assert output_dir is not None
    # The clean stage gets the bare prefix as --output-dir
    assert Path(output_dir).is_absolute(), (
        f"absolute prefix should stay absolute; got {output_dir!r}"
    )
    assert output_dir.startswith(abs_prefix)


def test_legacy_short_output_prefix_still_resolves_under_scripts(monkeypatch):
    """--output-prefix=output_X (no leading scripts/) preserves prior behavior:
    artifacts land under scripts/output_X*."""
    runner, captured = _capture_runner(monkeypatch)

    runner.run_pipeline(
        stages=["clean"],
        raw_dir="/tmp/test_raw_legacy",
        output_prefix="output_LegacyShortPrefix",
        dry_run=False,
    )

    args = captured[0][1]
    output_dir = _get_arg(args, "--output-dir")
    resolved = _resolve_against_scripts_cwd(output_dir, runner.script_dir)
    # Should land under scripts/, not scripts/scripts/ or repo-root-only
    assert "scripts/scripts" not in str(resolved)
    assert resolved.parent.name == "scripts" or resolved.is_relative_to(
        runner.script_dir
    ), f"legacy short prefix landed at unexpected location: {resolved}"


def test_raw_dir_with_scripts_prefix_does_not_double(monkeypatch):
    """Symmetric check: --raw-dir=scripts/... also must not double."""
    runner, captured = _capture_runner(monkeypatch)

    runner.run_pipeline(
        stages=["clean"],
        raw_dir="scripts/raw_data_test_only",
        output_prefix="scripts/products/output_RawDirTest",
        dry_run=False,
    )

    args = captured[0][1]
    input_dir = _get_arg(args, "--input-dir")
    resolved = _resolve_against_scripts_cwd(input_dir, runner.script_dir)
    assert "scripts/scripts" not in str(resolved), (
        f"--raw-dir doubled when subprocess CWD is scripts/: {resolved}"
    )


def test_resolve_path_scripts_prefix_is_repo_root_relative():
    """Unit test for _resolve_path: a 'scripts/'-prefixed relative path is
    resolved against the repo root, not script_dir."""
    runner = PipelineRunner()
    resolved = runner._resolve_path("scripts/products/output_X")
    # Must land at <repo_root>/scripts/products/output_X, NOT
    # <repo_root>/scripts/scripts/products/output_X
    assert "scripts/scripts" not in str(resolved)
    assert resolved == runner.script_dir / "products" / "output_X"
