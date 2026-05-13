"""Flutter bundle alignment — reads the bundled DB manifest from the
Flutter repo's committed git state.

Implements ADR-0001 HR-13 (committed-state-only validation) and provides
the data the P1.5 Gate 1 (bundle alignment) needs to compare against
``dist/export_manifest.json``.

Why committed state, not working tree
======================================
The 2026-05-12 incident happened because the bundle commit landed on the
wrong branch and never reached ``main``. Working-tree files looked correct
locally but the consumer (the user's iPhone) reads the bundle as published
to ``main``. The pipeline must validate against the same source of truth.

This module only reads from ``git show <branch>:<path>``. It never reads
the working tree. Uncommitted local changes are invisible to it by design.

Public API
==========
    read_flutter_bundle_manifest(flutter_repo_path, *, branch="main",
                                 manifest_path="assets/db/export_manifest.json")
        -> BundleManifestSnapshot

    check_bundle_alignment(flutter_repo_path, dist_db_version, *,
                           branch="main", manifest_path=...,
                           raise_on_misalignment=False)
        -> AlignmentResult

Branch is configurable (default ``main``). Fresh git repos may default to
``master``; that case raises ``BranchNotFoundError`` with the message
naming the requested branch so the operator can pass ``--branch master``
or fix git config.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union


DEFAULT_BRANCH = "main"
DEFAULT_MANIFEST_PATH = "assets/db/export_manifest.json"


# ---------------------------------------------------------------------------
# Exception hierarchy — every error carries actionable diagnostic info.
# ---------------------------------------------------------------------------


class BundleAlignmentError(Exception):
    """Base for all bundle-alignment errors."""


class FlutterRepoNotFoundError(BundleAlignmentError):
    """The flutter_repo_path does not exist or is not a git repository."""


class BranchNotFoundError(BundleAlignmentError):
    """The requested branch does not exist in the Flutter repo.

    Common cause: fresh git repos default to ``master`` instead of ``main``.
    The error message names the branch that was looked up so the operator
    can decide whether to pass a different branch name or fix
    ``git config init.defaultBranch``.
    """


class BundleManifestNotFoundError(BundleAlignmentError):
    """The branch exists but the manifest file is not present at that path
    on that branch's HEAD commit."""


class MalformedBundleManifestError(BundleAlignmentError):
    """The manifest file exists but the contents cannot be used:
    invalid JSON, wrong type at top-level, or missing required ``db_version``
    field."""


class BundleMisalignmentError(BundleAlignmentError):
    """Bundled-on-main version does not match dist version.

    Only raised by ``check_bundle_alignment(raise_on_misalignment=True)``.
    The default (False) returns an ``AlignmentResult`` with ``aligned=False``
    so the caller can decide how to surface it (P1.5 gate raises a
    structured GateFailure carrying this in its remediation message).
    """


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleManifestSnapshot:
    """A snapshot of the Flutter bundle manifest at a specific committed
    state.

    Attributes:
        flutter_repo_path: the repo root the snapshot was read from.
        branch: the branch name read.
        commit_sha: full SHA of the branch HEAD at read time. Lets the
            caller record exactly what state was validated even if the
            branch moves later.
        manifest_path: path within the repo (relative).
        db_version: required field from the manifest.
        db_checksum_sha256: optional checksum field; None if absent.
        raw: the full parsed manifest dict (for callers that need more).
    """

    flutter_repo_path: Path
    branch: str
    commit_sha: str
    manifest_path: str
    db_version: str
    db_checksum_sha256: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AlignmentResult:
    """Result of comparing bundled-on-main vs dist db_version.

    ``aligned`` is the only field that determines pass/fail; the other
    fields are present so audit logs (P1.5) can record exact context.
    """

    bundled_version: str
    dist_version: str
    aligned: bool
    branch: str
    bundled_commit_sha: str


# ---------------------------------------------------------------------------
# git command helper — single seam for monkeypatching in error-path tests
# ---------------------------------------------------------------------------


def _git(repo_path: Path, args: list) -> tuple:
    """Run a git command in ``repo_path``. Returns (returncode, stdout, stderr).

    Single seam — error-path tests monkeypatch this to inject failure
    conditions without requiring real git fixtures for every scenario.
    """
    proc = subprocess.run(
        ["git"] + args,
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_flutter_bundle_manifest(
    flutter_repo_path: Union[Path, str],
    *,
    branch: str = DEFAULT_BRANCH,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
) -> BundleManifestSnapshot:
    """Read the Flutter bundle manifest from the committed branch HEAD.

    Args:
        flutter_repo_path: filesystem path to the Flutter repo root.
        branch: branch name to read from. Default ``"main"``.
        manifest_path: path within the repo. Default
            ``"assets/db/export_manifest.json"``.

    Returns:
        ``BundleManifestSnapshot`` with the manifest contents AND the
        SHA of the branch HEAD at read time.

    Raises:
        FlutterRepoNotFoundError: path missing or not a git repo.
        BranchNotFoundError: requested branch does not exist.
        BundleManifestNotFoundError: file not on that branch.
        MalformedBundleManifestError: JSON broken or missing ``db_version``.
    """
    repo_path = Path(flutter_repo_path)

    # --- Step 1: path exists and is a directory --------------------------
    if not repo_path.exists():
        raise FlutterRepoNotFoundError(
            f"Flutter repo path does not exist: {repo_path}"
        )
    if not repo_path.is_dir():
        raise FlutterRepoNotFoundError(
            f"Flutter repo path exists but is not a directory: {repo_path}"
        )

    # --- Step 2: it's a git repo ----------------------------------------
    rc, _stdout, stderr = _git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    if rc != 0:
        raise FlutterRepoNotFoundError(
            f"Path is not a git repository: {repo_path}\n"
            f"  git stderr: {stderr.strip()}"
        )

    # --- Step 3: branch exists ------------------------------------------
    rc, _stdout, stderr = _git(repo_path, ["rev-parse", "--verify", f"{branch}^{{commit}}"])
    if rc != 0:
        raise BranchNotFoundError(
            f"Branch {branch!r} does not exist in {repo_path}.\n"
            f"  Fresh git repos may default to 'master' instead of 'main'. "
            f"If that applies, retry with --branch master, or fix the repo's\n"
            f"  default branch via: git config init.defaultBranch main\n"
            f"  git stderr: {stderr.strip()}"
        )

    # --- Step 4: capture branch HEAD SHA for audit ----------------------
    rc, stdout, stderr = _git(repo_path, ["rev-parse", branch])
    if rc != 0:
        # Should not happen given Step 3 succeeded, but fail loudly if it does.
        raise FlutterRepoNotFoundError(
            f"Unexpected git failure capturing branch SHA for {branch!r} "
            f"in {repo_path}: {stderr.strip()}"
        )
    commit_sha = stdout.strip()

    # --- Step 5: read manifest from branch HEAD via `git show` ----------
    rc, stdout, stderr = _git(
        repo_path,
        ["show", f"{branch}:{manifest_path}"],
    )
    if rc != 0:
        raise BundleManifestNotFoundError(
            f"Manifest {manifest_path!r} is not present on branch "
            f"{branch!r} in {repo_path}.\n"
            f"  This usually means a previous bundle commit was never made "
            f"to this branch — the pipeline cannot\n"
            f"  validate alignment without a manifest to read from.\n"
            f"  git stderr: {stderr.strip()}"
        )

    # --- Step 6: parse JSON and validate db_version ---------------------
    try:
        manifest = json.loads(stdout)
    except (json.JSONDecodeError, ValueError) as e:
        raise MalformedBundleManifestError(
            f"Manifest {manifest_path!r} on branch {branch!r} is not valid JSON: {e}\n"
            f"  repo: {repo_path}, commit: {commit_sha}"
        ) from e

    if not isinstance(manifest, dict):
        raise MalformedBundleManifestError(
            f"Manifest {manifest_path!r} top-level must be a JSON object, got "
            f"{type(manifest).__name__}.\n"
            f"  repo: {repo_path}, branch: {branch}, commit: {commit_sha}"
        )

    db_version = manifest.get("db_version")
    if not isinstance(db_version, str) or not db_version:
        raise MalformedBundleManifestError(
            f"Manifest {manifest_path!r} is missing or has invalid "
            f"'db_version' field: {db_version!r}.\n"
            f"  repo: {repo_path}, branch: {branch}, commit: {commit_sha}"
        )

    db_checksum = manifest.get("checksum_sha256")
    if db_checksum is not None and not isinstance(db_checksum, str):
        # Soft normalize: only accept a string or absence.
        db_checksum = None

    return BundleManifestSnapshot(
        flutter_repo_path=repo_path,
        branch=branch,
        commit_sha=commit_sha,
        manifest_path=manifest_path,
        db_version=db_version,
        db_checksum_sha256=db_checksum,
        raw=manifest,
    )


def check_bundle_alignment(
    flutter_repo_path: Union[Path, str],
    dist_db_version: str,
    *,
    branch: str = DEFAULT_BRANCH,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
    raise_on_misalignment: bool = False,
) -> AlignmentResult:
    """Compare the bundled-on-branch db_version against the dist db_version.

    Args:
        flutter_repo_path: filesystem path to the Flutter repo root.
        dist_db_version: the db_version freshly built into ``dist/``.
        branch: branch to read from. Default ``"main"``.
        manifest_path: path within the repo. Default
            ``"assets/db/export_manifest.json"``.
        raise_on_misalignment: if True, raise ``BundleMisalignmentError``
            when versions differ instead of returning ``aligned=False``.
            P1.5 gates use the False default so they can wrap the result
            in a structured GateFailure with their own remediation copy.

    Returns:
        ``AlignmentResult`` with ``aligned`` set accordingly.

    Raises:
        BundleMisalignmentError: only when ``raise_on_misalignment=True``
            AND versions differ. All read-side errors propagate from
            ``read_flutter_bundle_manifest``.
    """
    snapshot = read_flutter_bundle_manifest(
        flutter_repo_path,
        branch=branch,
        manifest_path=manifest_path,
    )
    aligned = snapshot.db_version == dist_db_version
    result = AlignmentResult(
        bundled_version=snapshot.db_version,
        dist_version=dist_db_version,
        aligned=aligned,
        branch=branch,
        bundled_commit_sha=snapshot.commit_sha,
    )
    if not aligned and raise_on_misalignment:
        raise BundleMisalignmentError(
            f"Bundle alignment FAILED.\n"
            f"  bundled (Flutter {branch} HEAD): {snapshot.db_version}\n"
            f"  dist (just-built):               {dist_db_version}\n"
            f"  flutter commit: {snapshot.commit_sha}\n"
            f"  manifest path:  {manifest_path}\n"
            "\n"
            f"The Flutter bundle on '{branch}' does not match the version this\n"
            "release built. Cleanup against this dist would delete blobs the\n"
            "bundled-on-main catalog still references (the 2026-05-12 failure\n"
            "mode). Either:\n"
            f"  - commit the new bundle to Flutter '{branch}' and re-run, or\n"
            "  - if you intentionally want to ship a different version,\n"
            "    rebuild dist to match what's bundled."
        )
    return result
