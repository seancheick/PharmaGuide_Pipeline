"""Tests for scripts/release_safety/protected_blobs.py — bundled∪dist
protected blob set computation (ADR-0001 P1.4 / interim before P3).

Test strategy (matches P1.3 pattern):
  - Real git repos for end-to-end union scenarios + the headline 2026-05-12
    regression. The trust model (committed manifest checksum gates working-
    tree DB content) is the safety primitive's whole point; mocking it would
    test only the mock.
  - Real on-disk fixtures for the dist side (no network).
  - The catalog DB is a minimal real SQLite file with the products_core
    schema needed by the validator's query.

Per the P1.4 sign-off:
  - "bundled missing" returns degenerate metadata; the gate-mode rejection
    lives in P1.5/P1.6, not in this module.
  - "checksum mismatch" hard-fails (LFS pointer is a special case of this).
  - Duplicate hashes are allowed (carried over from P1.2).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _h(idx: int) -> str:
    """Generate a deterministic 64-char lowercase hex hash for test readability.
    _h(0) = '0000...0000', _h(1) = '0000...0001', etc."""
    return f"{idx:064x}"


def _git_init(repo_path: Path, default_branch: str = "main") -> None:
    """Initialize a git repo with a known default branch + author identity."""
    subprocess.run(["git", "init", "-b", default_branch], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@release-safety.local"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Release-Safety Test"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_path, check=True, capture_output=True)


def _make_catalog_db(path: Path, blob_hashes: list) -> str:
    """Create a minimal SQLite catalog DB matching the products_core schema.
    Returns the SHA256 of the resulting file."""
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE products_core ("
            "  dsld_id TEXT PRIMARY KEY, "
            "  detail_blob_sha256 TEXT)"
        )
        for i, h in enumerate(blob_hashes):
            conn.execute("INSERT INTO products_core VALUES (?, ?)", (str(1000 + i), h))
        conn.commit()
    finally:
        conn.close()
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _commit_bundle(
    repo_path: Path,
    blob_hashes: list,
    db_version: str = "2026.05.12.bundled",
    *,
    write_catalog: bool = True,
    include_checksum: bool = True,
) -> dict:
    """Create + commit assets/db/{export_manifest.json, pharmaguide_core.db}.

    Args:
        write_catalog: when False, only the manifest is committed (simulates
            the LFS-pointer-or-missing scenario where the catalog file isn't
            actually present).
        include_checksum: when False, the manifest omits the checksum_sha256
            field — tests the degenerate "no checksum to verify against" path.
    """
    assets_db = repo_path / "assets" / "db"
    assets_db.mkdir(parents=True, exist_ok=True)

    manifest = {
        "db_version": db_version,
        "product_count": len(blob_hashes),
    }
    if write_catalog:
        catalog_path = assets_db / "pharmaguide_core.db"
        checksum = _make_catalog_db(catalog_path, blob_hashes)
        if include_checksum:
            manifest["checksum_sha256"] = checksum

    (assets_db / "export_manifest.json").write_text(json.dumps(manifest))
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"bundle {db_version}"], cwd=repo_path, check=True, capture_output=True)
    return manifest


def _make_dist(dist_dir: Path, blob_hashes: list, db_version: str = "2026.05.12.dist") -> None:
    """Create dist/detail_index.json + dist/export_manifest.json."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    detail_index = {}
    for i, h in enumerate(blob_hashes):
        dsld_id = str(1000 + i)
        detail_index[dsld_id] = {
            "blob_sha256": h,
            "storage_path": f"shared/details/sha256/{h[:2]}/{h}.json",
            "blob_version": 1,
        }
    (dist_dir / "detail_index.json").write_text(json.dumps(detail_index))
    (dist_dir / "export_manifest.json").write_text(json.dumps({
        "db_version": db_version,
        "checksum_sha256": "dist_side_irrelevant_for_p1_4",
    }))


# ---------------------------------------------------------------------------
# Test 1 — no overlap → union is sum, intersection 0
# ---------------------------------------------------------------------------


def test_p1_4_no_overlap_protected_set_is_sum(tmp_path):
    from release_safety.protected_blobs import compute_protected_blob_set

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    bundled_hashes = [_h(i) for i in range(3)]                # 0, 1, 2
    _commit_bundle(flutter_repo, bundled_hashes, db_version="vBUNDLED")

    dist_dir = tmp_path / "dist"
    dist_hashes = [_h(i) for i in range(10, 13)]              # 10, 11, 12 — no overlap
    _make_dist(dist_dir, dist_hashes, db_version="vDIST")

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    assert result.degenerate is False
    assert result.bundled_count == 3
    assert result.dist_count == 3
    assert result.union_count == 6
    assert result.intersection_count == 0
    assert result.protected == frozenset(bundled_hashes + dist_hashes)
    assert result.bundled_version == "vBUNDLED"
    assert result.dist_version == "vDIST"


# ---------------------------------------------------------------------------
# Test 2 — full overlap → union equals either side, intersection equals both
# ---------------------------------------------------------------------------


def test_p1_4_full_overlap_protected_set_equals_either(tmp_path):
    from release_safety.protected_blobs import compute_protected_blob_set

    shared = [_h(i) for i in range(5)]
    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, shared, db_version="vSAME")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, shared, db_version="vSAME")

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    assert result.degenerate is False
    assert result.bundled_hashes == result.dist_hashes == frozenset(shared)
    assert result.union_count == 5
    assert result.intersection_count == 5
    assert result.protected == frozenset(shared)


# ---------------------------------------------------------------------------
# Test 3 — partial overlap → metrics correct
# ---------------------------------------------------------------------------


def test_p1_4_partial_overlap_metrics(tmp_path):
    from release_safety.protected_blobs import compute_protected_blob_set

    bundled = [_h(i) for i in range(0, 5)]    # 0..4
    dist    = [_h(i) for i in range(3, 8)]    # 3..7  (3, 4 shared with bundled)

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled)

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, dist)

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    assert result.degenerate is False
    assert result.bundled_count == 5
    assert result.dist_count == 5
    assert result.union_count == 8                      # 0..7
    assert result.intersection_count == 2               # 3, 4
    assert result.protected == frozenset([_h(i) for i in range(0, 8)])


# ---------------------------------------------------------------------------
# Test 4 — same db_version + same hash sets → fully aligned
# ---------------------------------------------------------------------------


def test_p1_4_same_version_full_alignment(tmp_path):
    """The post-bundle-commit steady state: bundled-on-main matches dist
    exactly (version + hashes). Protected set degenerates to that one set;
    both sources contribute everything."""
    from release_safety.protected_blobs import compute_protected_blob_set

    hashes = [_h(i) for i in range(7)]
    version = "2026.05.12.203133"

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, hashes, db_version=version)

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, hashes, db_version=version)

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    assert result.degenerate is False
    assert result.bundled_version == version
    assert result.dist_version == version
    assert result.bundled_hashes == result.dist_hashes
    assert result.union_count == result.intersection_count == 7


# ---------------------------------------------------------------------------
# Test 5 — bundled missing → degenerate dry-run metadata (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario,setup_fn",
    [
        ("manifest_not_committed",     "no_bundle"),
        ("catalog_file_missing",       "manifest_only"),
        ("manifest_lacks_checksum",    "no_checksum"),
    ],
)
def test_p1_4_bundled_missing_returns_degenerate_metadata(tmp_path, scenario, setup_fn):
    """Three flavors of "bundled side absent" all converge on the same
    return shape: degenerate=True, populated degenerate_reason, protected
    set equals dist hashes only.

    Per P1.4 sign-off: P1.4 returns degenerate metadata; P1.5/P1.6 reject
    this for --execute. P1.4 itself does NOT raise on these cases.
    """
    from release_safety.protected_blobs import compute_protected_blob_set

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)

    if setup_fn == "no_bundle":
        # Just an unrelated commit; no assets/db/ at all.
        (flutter_repo / "README").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=flutter_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=flutter_repo, check=True, capture_output=True)
    elif setup_fn == "manifest_only":
        # Manifest committed but catalog DB never written.
        _commit_bundle(flutter_repo, [_h(0), _h(1)], write_catalog=False)
    elif setup_fn == "no_checksum":
        # Manifest + catalog committed but manifest omits checksum_sha256.
        _commit_bundle(flutter_repo, [_h(0), _h(1)], include_checksum=False)

    dist_dir = tmp_path / "dist"
    dist_hashes = [_h(i) for i in range(20, 23)]
    _make_dist(dist_dir, dist_hashes, db_version="vDIST")

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    assert result.degenerate is True, scenario
    assert result.degenerate_reason is not None
    assert result.bundled_hashes == frozenset()
    assert result.bundled_version is None
    assert result.bundled_commit_sha is None
    # Dist still came through, fully usable.
    assert result.dist_hashes == frozenset(dist_hashes)
    assert result.protected == frozenset(dist_hashes)
    # Reason text must be non-trivial — operators read it.
    assert len(result.degenerate_reason) > 20


# ---------------------------------------------------------------------------
# Test 6 — dist missing → fail closed (no degenerate path for dist)
# ---------------------------------------------------------------------------


def test_p1_4_dist_missing_fails_closed(tmp_path):
    """Dist is REQUIRED. Missing dist/detail_index.json propagates as
    MalformedJSONError from validate_detail_index — there is no degenerate
    metadata path for the dist side."""
    from release_safety.protected_blobs import compute_protected_blob_set
    from release_safety.index_validator import MalformedJSONError

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, [_h(0)])

    # dist_dir doesn't exist OR exists with no detail_index.json
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    # NB: no detail_index.json written

    with pytest.raises(MalformedJSONError):
        compute_protected_blob_set(flutter_repo, dist_dir)


# ---------------------------------------------------------------------------
# Test 7 — duplicate hashes in bundled catalog allowed; frozenset dedups
# ---------------------------------------------------------------------------


def test_p1_4_duplicate_blob_hashes_in_bundled_catalog_allowed(tmp_path):
    """Two products in the bundled catalog with identical detail_blob_sha256
    is legitimate (content-addressed; identical detail JSON). The frozenset
    naturally dedups; bundled_count reports the duplicates so audit logs
    can see them."""
    from release_safety.protected_blobs import compute_protected_blob_set

    # 5 dsld_ids but only 3 unique hashes (idx 0 and idx 1 each appear twice)
    bundled_with_dups = [_h(0), _h(0), _h(1), _h(1), _h(2)]

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled_with_dups, db_version="vBUNDLED")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, [_h(2), _h(3)], db_version="vDIST")

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    assert result.degenerate is False
    # Bundled side: 5 rows, 3 unique hashes
    assert result.bundled_count == 5
    assert result.bundled_hashes == frozenset([_h(0), _h(1), _h(2)])
    # Union: 4 unique
    assert result.union_count == 4
    # Intersection: just _h(2)
    assert result.intersection_count == 1


# ---------------------------------------------------------------------------
# Test 8 — LFS pointer / checksum mismatch → fails closed (HARD ERROR)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario,catalog_replacement",
    [
        ("lfs_pointer_text",     b"version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\nsize 12345\n"),
        ("local_modification",   b"this is some other arbitrary content not the real DB"),
        ("empty_file",           b""),
    ],
)
def test_p1_4_lfs_pointer_or_checksum_mismatch_fails_closed(tmp_path, scenario, catalog_replacement):
    """Working-tree catalog DB content has a SHA256 that does NOT match the
    committed manifest checksum. P1.4 must HARD FAIL with
    MalformedBundleCatalogError — the file IS present so this is not the
    degenerate "absence" case; it is corruption / wrong content / LFS pointer.

    The error message must explain the LFS-pointer scenario (operators
    will hit this most often when they forget `git lfs pull`)."""
    from release_safety.protected_blobs import (
        compute_protected_blob_set,
        MalformedBundleCatalogError,
    )

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    # Commit a real catalog + manifest (with valid checksum_sha256)
    _commit_bundle(flutter_repo, [_h(0), _h(1), _h(2)], db_version="vBUNDLED")

    # Now poison the working-tree catalog (committed manifest checksum unchanged)
    wt_catalog = flutter_repo / "assets" / "db" / "pharmaguide_core.db"
    wt_catalog.write_bytes(catalog_replacement)

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, [_h(0)], db_version="vDIST")

    with pytest.raises(MalformedBundleCatalogError) as excinfo:
        compute_protected_blob_set(flutter_repo, dist_dir)

    msg = str(excinfo.value)
    # Operator-actionable diagnostics in the error message:
    assert "SHA256 does not match" in msg, scenario
    assert "git lfs pull" in msg, (
        f"LFS pointer remediation must be named in the error message "
        f"(scenario={scenario})"
    )
    assert str(wt_catalog) in msg


# ---------------------------------------------------------------------------
# Test 9 — checksum match allows DB read (positive control)
# ---------------------------------------------------------------------------


def test_p1_4_checksum_match_allows_db_read(tmp_path):
    """Sanity check: when working-tree DB SHA256 matches committed
    manifest checksum, the SQLite query proceeds and bundled_hashes
    are populated. Without this passing, every other test that uses
    _commit_bundle would silently degrade."""
    from release_safety.protected_blobs import compute_protected_blob_set

    bundled = [_h(0), _h(1), _h(2)]
    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled, db_version="vCHECK")

    # Working tree IS the committed catalog (we just committed it; no further
    # changes). Checksum must match.

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, [_h(99)], db_version="vDIST")

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    assert result.degenerate is False
    assert result.degenerate_reason is None
    assert result.bundled_hashes == frozenset(bundled)
    assert result.bundled_count == 3


# ---------------------------------------------------------------------------
# Test 10 — May 12 regression: bundled-only hashes remain protected
# ---------------------------------------------------------------------------


def test_p1_4_2026_05_12_regression_bundled_only_hashes_protected(tmp_path):
    """THE HEADLINE REGRESSION TEST.

    Replays the shape of the 2026-05-12 incident:
      - bundled-on-main has version v2026.05.11.* with hashes [A, B, C, D, E, F, G, H, I, J]
      - dist has version v2026.05.12.* with hashes [F, G, H, I, J, K, L, M, N, O]
      - 5 hashes overlap (F-J); 5 unique to bundled (A-E); 5 unique to dist (K-O)

    Without P1.4 (today's broken cleanup): protection = dist only → A-E
      get deleted → bundled-on-main blob fetches return 404 → product
      detail screens go empty → user-visible bug.

    With P1.4: protection = bundled ∪ dist = A-O (all 15) → A-E are
      protected → no deletion → consumers stay safe.

    This test asserts the union math is correct AND the bundled-only
    hashes specifically are in the protected set. If this test fails,
    P1.4 does not solve the failure mode.
    """
    from release_safety.protected_blobs import compute_protected_blob_set

    bundled_only = [_h(i) for i in range(0, 5)]      # A..E
    overlap      = [_h(i) for i in range(5, 10)]     # F..J
    dist_only    = [_h(i) for i in range(10, 15)]    # K..O

    bundled_hashes = bundled_only + overlap          # 10 hashes total
    dist_hashes    = overlap + dist_only             # 10 hashes total

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled_hashes, db_version="2026.05.11.bundled")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, dist_hashes, db_version="2026.05.12.dist")

    result = compute_protected_blob_set(flutter_repo, dist_dir)

    # Sanity: not degenerate
    assert result.degenerate is False, (
        "Bundled side did not load — the regression test is meaningless if "
        "bundled is degenerate. Fix the fixture before reading further."
    )

    # The headline assertion: every bundled-only hash MUST be in protected.
    # If this fails, cleanup based on this set would have nuked them on May 12.
    for h in bundled_only:
        assert h in result.protected, (
            f"P1.4 REGRESSION: bundled-only hash {h[:16]}... is NOT in "
            f"the protected set. This is the exact 2026-05-12 failure mode."
        )

    # Overlap and dist-only are also protected (sanity).
    for h in overlap + dist_only:
        assert h in result.protected

    # Metrics math
    assert result.bundled_count == 10
    assert result.dist_count == 10
    assert result.union_count == 15
    assert result.intersection_count == 5
    assert result.bundled_version == "2026.05.11.bundled"
    assert result.dist_version == "2026.05.12.dist"
