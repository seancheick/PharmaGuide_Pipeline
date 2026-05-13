"""Tests for scripts/release_safety/bundle_alignment.py — Flutter bundle
alignment (ADR-0001 P1.3 / HR-13).

Mixed test strategy (per P1.3 sign-off):

  - Trust-model tests use REAL git repos (set up in tmp_path via the
    ``fake_flutter_repo`` fixture). These tests are the authoritative
    coverage of HR-13: "validation must derive from committed git state,
    never working tree." Mocking the git seam would prove only that the
    mock works.

  - Error-path tests where setting up real-git failure conditions is
    awkward (subprocess returning specific non-zero codes, garbage JSON
    body, etc.) monkeypatch the ``_git`` seam. These tests verify the
    error-handling logic, not git semantics.

Requires ``git`` on PATH (already a hard pipeline dependency).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _git_init(repo_path: Path, default_branch: str = "main") -> None:
    """Initialize a git repo with a known default branch + author identity."""
    subprocess.run(
        ["git", "init", "-b", default_branch],
        cwd=repo_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@release-safety.local"],
        cwd=repo_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Release-Safety Test"],
        cwd=repo_path, check=True, capture_output=True,
    )
    # Disable signing so tests pass in environments with default gpgsign=true.
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo_path, check=True, capture_output=True,
    )


def _commit_manifest(repo_path: Path, manifest: dict, message: str = "bundle update") -> str:
    """Write assets/db/export_manifest.json + commit it. Returns the SHA."""
    assets_db = repo_path / "assets" / "db"
    assets_db.mkdir(parents=True, exist_ok=True)
    manifest_path = assets_db / "export_manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path, check=True, capture_output=True,
    )
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path, check=True, capture_output=True, text=True,
    ).stdout.strip()
    return sha


@pytest.fixture
def fake_flutter_repo(tmp_path):
    """A real git repo at tmp_path with a manifest committed to ``main``.

    Returns (repo_path, committed_db_version, commit_sha).
    """
    _git_init(tmp_path, default_branch="main")
    manifest = {
        "db_version": "2026.05.12.203133",
        "checksum_sha256": "abc123def456",
        "product_count": 8331,
    }
    sha = _commit_manifest(tmp_path, manifest, message="bundle v2026.05.12.203133")
    return tmp_path, manifest["db_version"], sha


# ---------------------------------------------------------------------------
# Trust-model tests — REAL git repos
# ---------------------------------------------------------------------------


def test_p1_3_real_read_committed_manifest(fake_flutter_repo):
    """End-to-end: read_flutter_bundle_manifest pulls db_version, checksum,
    and commit SHA from committed main HEAD in a real git repo."""
    from release_safety.bundle_alignment import read_flutter_bundle_manifest

    repo_path, expected_version, expected_sha = fake_flutter_repo

    snapshot = read_flutter_bundle_manifest(repo_path)

    assert snapshot.flutter_repo_path == repo_path
    assert snapshot.branch == "main"
    assert snapshot.commit_sha == expected_sha
    assert snapshot.db_version == expected_version
    assert snapshot.db_checksum_sha256 == "abc123def456"
    assert snapshot.raw["product_count"] == 8331


def test_p1_3_real_check_alignment_aligned(fake_flutter_repo):
    """When dist db_version matches main HEAD's bundled version,
    AlignmentResult.aligned is True."""
    from release_safety.bundle_alignment import check_bundle_alignment

    repo_path, version, sha = fake_flutter_repo

    result = check_bundle_alignment(repo_path, dist_db_version=version)

    assert result.aligned is True
    assert result.bundled_version == version
    assert result.dist_version == version
    assert result.branch == "main"
    assert result.bundled_commit_sha == sha


def test_p1_3_real_check_alignment_misaligned_no_raise(fake_flutter_repo):
    """When versions differ and raise_on_misalignment is False (default),
    AlignmentResult is returned with aligned=False — no exception."""
    from release_safety.bundle_alignment import check_bundle_alignment

    repo_path, bundled_version, _sha = fake_flutter_repo

    result = check_bundle_alignment(
        repo_path,
        dist_db_version="2026.05.13.999999",  # newer than bundled
    )

    assert result.aligned is False
    assert result.bundled_version == bundled_version
    assert result.dist_version == "2026.05.13.999999"


def test_p1_3_real_check_alignment_misaligned_with_raise_replays_2026_05_12(fake_flutter_repo):
    """Replaying the 2026-05-12 scenario shape: bundled-on-main is one
    version, dist is the newer version. With raise_on_misalignment=True,
    we get a BundleMisalignmentError that names BOTH versions and the
    bundled commit SHA — exactly the diagnostic P1.5 will surface to
    the operator."""
    from release_safety.bundle_alignment import (
        check_bundle_alignment,
        BundleMisalignmentError,
    )

    repo_path, bundled_version, sha = fake_flutter_repo
    dist_version = "2026.05.12.203133-newer"

    with pytest.raises(BundleMisalignmentError) as excinfo:
        check_bundle_alignment(
            repo_path,
            dist_db_version=dist_version,
            raise_on_misalignment=True,
        )

    msg = str(excinfo.value)
    assert bundled_version in msg
    assert dist_version in msg
    assert sha in msg
    # Operator-actionable remediation must be in the message.
    assert "commit the new bundle" in msg


def test_p1_3_real_reads_committed_state_not_working_tree(fake_flutter_repo):
    """HR-13 regression: modify the working-tree manifest WITHOUT
    committing. read_flutter_bundle_manifest must still return the
    COMMITTED value from main HEAD, NOT the working-tree value.

    This is the headline test for the trust model — the entire 2026-05-12
    incident exists because the pipeline trusted working-tree-equivalent
    state instead of committed state.
    """
    from release_safety.bundle_alignment import read_flutter_bundle_manifest

    repo_path, committed_version, _sha = fake_flutter_repo

    # Modify working tree without committing.
    wt_manifest = repo_path / "assets" / "db" / "export_manifest.json"
    wt_manifest.write_text(json.dumps({
        "db_version": "WORKING_TREE_POISONED_VALUE_must_not_be_read",
        "checksum_sha256": "should_be_ignored",
    }))

    # Confirm the working tree IS poisoned (sanity).
    assert "WORKING_TREE_POISONED" in wt_manifest.read_text()

    # The function MUST return the committed value, not the working-tree value.
    snapshot = read_flutter_bundle_manifest(repo_path)

    assert snapshot.db_version == committed_version
    assert "POISONED" not in snapshot.db_version
    assert snapshot.db_checksum_sha256 == "abc123def456"   # original committed checksum
    # Working tree must be unchanged by the read (we don't restore files).
    assert "WORKING_TREE_POISONED" in wt_manifest.read_text()


def test_p1_3_real_branch_not_found_uses_helpful_error(tmp_path):
    """When asked for ``main`` but the repo only has ``master``, raise
    BranchNotFoundError with a message that names both the requested
    branch and the master-default workaround (per P1.3 sign-off
    requirement #2)."""
    from release_safety.bundle_alignment import (
        read_flutter_bundle_manifest,
        BranchNotFoundError,
    )

    # Fresh repo with master as the default branch (no main).
    _git_init(tmp_path, default_branch="master")
    _commit_manifest(tmp_path, {"db_version": "irrelevant"}, message="master commit")

    with pytest.raises(BranchNotFoundError) as excinfo:
        read_flutter_bundle_manifest(tmp_path, branch="main")

    msg = str(excinfo.value)
    assert "'main'" in msg or "main" in msg
    # Helpful workaround named in the error.
    assert "master" in msg
    assert "init.defaultBranch" in msg


def test_p1_3_real_configurable_branch_master(tmp_path):
    """When the repo uses master, passing branch='master' reads it
    successfully. Configurable branch (P1.3 requirement #1)."""
    from release_safety.bundle_alignment import read_flutter_bundle_manifest

    _git_init(tmp_path, default_branch="master")
    _commit_manifest(tmp_path, {"db_version": "2026.05.12.master.X"}, message="master commit")

    snapshot = read_flutter_bundle_manifest(tmp_path, branch="master")

    assert snapshot.branch == "master"
    assert snapshot.db_version == "2026.05.12.master.X"


# ---------------------------------------------------------------------------
# Error-path tests — mocked _git seam
# ---------------------------------------------------------------------------


def test_p1_3_path_does_not_exist(tmp_path):
    """Non-existent flutter_repo_path raises FlutterRepoNotFoundError."""
    from release_safety.bundle_alignment import (
        read_flutter_bundle_manifest,
        FlutterRepoNotFoundError,
    )

    bogus = tmp_path / "definitely_does_not_exist"

    with pytest.raises(FlutterRepoNotFoundError) as excinfo:
        read_flutter_bundle_manifest(bogus)

    assert str(bogus) in str(excinfo.value)


def test_p1_3_path_exists_but_not_git(tmp_path):
    """Path exists but no .git directory → FlutterRepoNotFoundError."""
    from release_safety.bundle_alignment import (
        read_flutter_bundle_manifest,
        FlutterRepoNotFoundError,
    )

    (tmp_path / "some_file").write_text("hello")
    # Deliberately no `git init`.

    with pytest.raises(FlutterRepoNotFoundError) as excinfo:
        read_flutter_bundle_manifest(tmp_path)

    assert "not a git repository" in str(excinfo.value)


def test_p1_3_manifest_not_in_branch_via_mock(monkeypatch, tmp_path):
    """When git show returns non-zero with file-missing stderr, raise
    BundleManifestNotFoundError. Mocked because constructing this real-git
    case is awkward (needs a branch with a commit but no manifest path)."""
    from release_safety import bundle_alignment
    from release_safety.bundle_alignment import (
        read_flutter_bundle_manifest,
        BundleManifestNotFoundError,
    )

    # Real fixture for path/branch validation, but mock _git for the final read.
    _git_init(tmp_path, default_branch="main")
    # Create some unrelated commit so the branch exists.
    (tmp_path / "readme").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    real_git = bundle_alignment._git
    def fake_git(repo, args):
        # Pass through everything except `show <branch>:<path>`.
        if len(args) >= 2 and args[0] == "show" and ":" in args[1]:
            return 128, "", "fatal: path 'assets/db/export_manifest.json' does not exist in 'main'"
        return real_git(repo, args)
    monkeypatch.setattr(bundle_alignment, "_git", fake_git)

    with pytest.raises(BundleManifestNotFoundError) as excinfo:
        read_flutter_bundle_manifest(tmp_path)

    msg = str(excinfo.value)
    assert "assets/db/export_manifest.json" in msg
    assert "main" in msg
    assert "not present on branch" in msg


def test_p1_3_malformed_manifest_json_via_mock(monkeypatch, tmp_path):
    """When git show returns garbage instead of valid JSON, raise
    MalformedBundleManifestError. Mocked because committing garbage JSON
    to a real repo is fragile (git-add of a malformed file may still work
    but the test point is the parser's response)."""
    from release_safety import bundle_alignment
    from release_safety.bundle_alignment import (
        read_flutter_bundle_manifest,
        MalformedBundleManifestError,
    )

    _git_init(tmp_path, default_branch="main")
    _commit_manifest(tmp_path, {"db_version": "x"}, message="init")

    real_git = bundle_alignment._git
    def fake_git(repo, args):
        if len(args) >= 2 and args[0] == "show" and ":" in args[1]:
            return 0, "THIS IS NOT JSON {{{", ""
        return real_git(repo, args)
    monkeypatch.setattr(bundle_alignment, "_git", fake_git)

    with pytest.raises(MalformedBundleManifestError) as excinfo:
        read_flutter_bundle_manifest(tmp_path)

    assert "not valid JSON" in str(excinfo.value)


def test_p1_3_manifest_missing_db_version_via_mock(monkeypatch, tmp_path):
    """Manifest parses as JSON but lacks the required db_version field →
    MalformedBundleManifestError. Also covered: non-string db_version."""
    from release_safety import bundle_alignment
    from release_safety.bundle_alignment import (
        read_flutter_bundle_manifest,
        MalformedBundleManifestError,
    )

    _git_init(tmp_path, default_branch="main")
    _commit_manifest(tmp_path, {"db_version": "x"}, message="init")

    real_git = bundle_alignment._git

    # Case A: missing db_version entirely
    def fake_git_missing(repo, args):
        if len(args) >= 2 and args[0] == "show" and ":" in args[1]:
            return 0, json.dumps({"checksum_sha256": "abc"}), ""
        return real_git(repo, args)
    monkeypatch.setattr(bundle_alignment, "_git", fake_git_missing)
    with pytest.raises(MalformedBundleManifestError) as excinfo:
        read_flutter_bundle_manifest(tmp_path)
    assert "db_version" in str(excinfo.value)

    # Case B: db_version present but wrong type
    def fake_git_wrong_type(repo, args):
        if len(args) >= 2 and args[0] == "show" and ":" in args[1]:
            return 0, json.dumps({"db_version": 12345}), ""
        return real_git(repo, args)
    monkeypatch.setattr(bundle_alignment, "_git", fake_git_wrong_type)
    with pytest.raises(MalformedBundleManifestError) as excinfo:
        read_flutter_bundle_manifest(tmp_path)
    assert "db_version" in str(excinfo.value)
