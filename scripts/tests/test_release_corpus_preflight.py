#!/usr/bin/env python3
"""A skipped canary is not a passing canary.

A clean source worktree has no product corpus and no canary baselines, so the
catalog-backed invariant tests pytest.skip(). For `fast` that is correct — it
proves SOURCE integrity and says nothing about the catalog. On the release path
it is the wrong answer: the run reports green while the tests that compare a
rebuild against its baseline never executed.

The 2026-09-18 convergence surfaced this concretely — a clean worktree reported
"15672 passed, 191 skipped, 0 failed", which reads as release-grade and is not.

So the release tier requires the corpus and fails hard without it. These tests
exercise the shell function directly, in both directions, because a gate that
only ever fails is as useless as one that only ever passes.
"""
from __future__ import annotations

import subprocess
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TEST_SH = REPO / "scripts" / "test.sh"

#: Mirrors CANARY_IDS in test_e1_2_2_preflight_invariant.py.
CANARY_IDS = ["35491", "306237", "246324", "1002", "19067", "1036",
              "176872", "266975", "19055"]


def _corpus_check_source() -> str:
    script = TEST_SH.read_text(encoding="utf-8")
    start = script.index("release_preflight_corpus_check() {")
    end = script.index("\nrelease_preflight_staleness_check() {")
    return script[start:end]


def _run(repo_root: Path, env_extra: str = "") -> subprocess.CompletedProcess:
    owner = repo_root / "scripts" / "release_artifact_paths.py"
    owner.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "scripts" / "release_artifact_paths.py", owner)
    harness = (
        f'REPO_ROOT="{repo_root}"\nPG_PYTHON="{sys.executable}"\n{env_extra}\n'
        f'{_corpus_check_source()}\nrelease_preflight_corpus_check\n'
    )
    return subprocess.run(["bash", "-c", harness], capture_output=True, text=True)


def test_the_gate_passes_when_the_canonical_corpus_is_present(tmp_path):
    products = tmp_path / "scripts" / "products"
    products.mkdir(parents=True)
    from scripts.release_artifact_paths import canary_baseline_dir
    baselines = canary_baseline_dir(tmp_path)
    baselines.mkdir(parents=True)
    for dsld_id in CANARY_IDS:
        (baselines / f"{dsld_id}.json").write_text("{}")

    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr


def test_a_missing_corpus_is_a_hard_failure_not_a_skip(tmp_path):
    result = _run(tmp_path)

    assert result.returncode != 0
    assert "REQUIRED PRODUCT CORPUS IS MISSING" in result.stderr
    # The message must say why a skip would have been wrong.
    assert "skipped canary is not a passing canary" in result.stderr


def test_a_half_populated_corpus_still_fails(tmp_path):
    """Directories present but baselines incomplete must not pass — that is the
    shape that would otherwise skip a subset and still report green."""
    (tmp_path / "scripts" / "products").mkdir(parents=True)
    from scripts.release_artifact_paths import canary_baseline_dir
    baselines = canary_baseline_dir(tmp_path)
    baselines.mkdir(parents=True)
    for dsld_id in CANARY_IDS[:-2]:            # two short
        (baselines / f"{dsld_id}.json").write_text("{}")

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "canary baselines" in result.stderr
    for missing in CANARY_IDS[-2:]:
        assert missing in result.stderr


def test_the_bypass_is_explicit_and_announces_itself(tmp_path):
    """A corpus-less release run must be a deliberate, visible choice."""
    result = _run(tmp_path, env_extra="PG_ALLOW_MISSING_CORPUS=1")

    assert result.returncode == 0
    assert "bypassed" in result.stderr


def test_the_release_tier_actually_calls_the_gate():
    """The function existing is not the contract; being wired in is."""
    script = TEST_SH.read_text(encoding="utf-8")
    release_block = script[script.index("\n  release)"):script.index("\n  full)")]

    assert "release_preflight_corpus_check" in release_block


def test_the_gate_and_invariant_use_one_active_baseline_owner():
    invariant = (REPO / "scripts" / "tests"
                 / "test_e1_2_2_preflight_invariant.py").read_text(encoding="utf-8")
    assert "BASELINE_DIR = canary_baseline_dir(ROOT)" in invariant
    assert "from release_artifact_paths import canary_baseline_dir" in _corpus_check_source()


def test_stale_root_baselines_cannot_hide_a_missing_active_baseline(tmp_path):
    """Nine obsolete root files cannot stand in for the invariant's dated owner."""
    (tmp_path / "scripts" / "products").mkdir(parents=True)
    stale = tmp_path / "reports" / "baseline_pre_e1_2_2"
    stale.mkdir(parents=True)
    for dsld_id in CANARY_IDS:
        (stale / f"{dsld_id}.json").write_text("{}")

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "canary baselines" in result.stderr
