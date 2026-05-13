"""Protected blob set computation — bundled∪dist∪registry union for orphan-cleanup gating.

Implements ADR-0001 P1.4 + P3.5.

P1.4 shipped the interim bundled∪dist heuristic. P3.5 adds the third source:
catalog_releases registry rows in state ∈ {ACTIVE, VALIDATING}. The union
is purely additive — protected set only grows. ``dist_dir`` remains an
honored input until P3.6 has been observed through at least one clean
release cycle, at which point a follow-up commit can drop it.

Why three sources
=================
The 2026-05-12 incident proved that orphan cleanup must protect blobs
referenced by *any* catalog a consumer could currently be reading — not
just dist's catalog. The three sources together cover:

  - **bundled** (Flutter main HEAD): the catalog installed on shipped app
    builds. Always required (degenerate-tolerant for absence).
  - **dist** (just-built pipeline output): the catalog about to be uploaded.
    Always required. Transitional until P3.6.
  - **registry** (Supabase catalog_releases ∩ {ACTIVE, VALIDATING}): every
    catalog currently routed to consumers, plus any that are mid-activation.
    Added in P3.5. Becomes load-bearing once backfill (P3.3) is run.

VALIDATING is included because the row's blobs MUST stay protected during
the activation window — between PENDING→VALIDATING and VALIDATING→ACTIVE,
the blobs are written to Supabase but the row is not yet ACTIVE. An orphan
sweep that runs in that window could delete blobs the operator is about to
promote to ACTIVE, recreating the 2026-05-12 race in a new form.

Trust model — Option C (per P1.4 sign-off, ADR HR-13)
======================================================
The bundled catalog DB (``assets/db/pharmaguide_core.db``) is Git LFS-
tracked in the Flutter repo. ``git show <branch>:<lfs-tracked-file>``
returns the LFS pointer text, NOT the SQLite content. Two avenues
were considered:

  - LFS smudge: adds an external dependency on git-lfs tooling and
    requires LFS objects to be locally downloaded. Rejected.
  - Bundle the detail_index.json into the Flutter repo: forward-looking
    improvement requiring a Flutter-side bundle-format change. Out of
    P1.4 scope.

P1.4 uses Option C: read the working-tree catalog DB but verify its
SHA256 against the committed manifest's ``checksum_sha256``. This keeps
trust anchored in committed git state (the manifest's recorded checksum)
without depending on LFS, while letting us actually query the SQLite
content.

Behavior summary
================
- Dist side is REQUIRED. Anything wrong with dist (missing, malformed,
  unparseable) hard-fails — we cannot validate cleanup against an
  unreliable dist.
- Bundled side is degenerate-tolerant for ABSENCE (no manifest on main,
  no catalog file in working tree, manifest lacks checksum field) —
  the result is returned with ``degenerate=True`` and a human-readable
  ``degenerate_reason``. **P1.5/P1.6 must reject degenerate protection
  during --execute** (this module doesn't know which mode it was called from).
- Bundled side hard-fails on CORRUPTION (malformed manifest, working-tree
  catalog SHA256 doesn't match committed manifest checksum). Includes
  the LFS-pointer scenario as a checksum mismatch.

Public API
==========
    compute_protected_blob_set(
        flutter_repo_path,
        dist_dir,
        *, branch="main",
        bundled_manifest_path="assets/db/export_manifest.json",
        bundled_catalog_path="assets/db/pharmaguide_core.db",
        dist_manifest_filename="export_manifest.json",
        dist_index_filename="detail_index.json",
        supabase_client=None,                  # P3.5: enables registry side
        registry_bucket="pharmaguide",         # P3.5
        registry_table="catalog_releases",     # P3.5
    ) -> ProtectedBlobSet

When ``supabase_client`` is ``None`` the registry side is a no-op and the
function returns the P1.4 bundled∪dist set. When a client is provided,
the function additionally fetches every ACTIVE+VALIDATING row, downloads
its ``detail_index_url`` from Supabase storage, validates it, and unions
its hashes into ``protected``.

Registry-side failure modes (P3.5)
==================================
  - Missing index in storage      -> RegistryDetailIndexMissingError (hard fail)
    The registry row promises a path the bucket does not contain. Operator
    must retire the row OR upload the missing index before cleanup can run.
  - Malformed registry index      -> IndexValidationError subclass (hard fail)
    Same policy as dist. The index is present but unparseable.
  - Storage fetch/network error   -> RegistryFetchError (raised, fail closed)
    No silent retry at this layer; the gates orchestrator decides whether
    to re-run.

  RETIRED and PENDING rows are explicitly excluded from the union — their
  blobs are not consumer-routed (RETIRED) or not yet uploaded (PENDING).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Union

from .bundle_alignment import (
    DEFAULT_BRANCH,
    DEFAULT_MANIFEST_PATH,
    BranchNotFoundError,
    BundleManifestNotFoundError,
    FlutterRepoNotFoundError,
    MalformedBundleManifestError,
    read_flutter_bundle_manifest,
)
from .index_validator import validate_detail_index

DEFAULT_BUNDLED_CATALOG_PATH = "assets/db/pharmaguide_core.db"
DEFAULT_DIST_INDEX_FILENAME = "detail_index.json"
DEFAULT_DIST_MANIFEST_FILENAME = "export_manifest.json"
DEFAULT_REGISTRY_BUCKET = "pharmaguide"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class ProtectedBlobSetError(Exception):
    """Base for protected-blob-set computation errors."""


class MalformedBundleCatalogError(ProtectedBlobSetError):
    """Working-tree catalog DB exists but its SHA256 does not match the
    committed manifest's ``checksum_sha256``.

    Common causes (named in error message):
      - LFS pointer: the working-tree file is the Git LFS pointer text,
        not the actual SQLite content. Run ``git lfs pull``.
      - Local modifications: the catalog DB was edited (drift codegen,
        manual edit, etc.) without a re-bundle.
      - Stale checkout: working tree is on a different branch than the
        one whose committed manifest we read.

    This is a HARD failure (not degenerate). The catalog file IS present,
    but we cannot trust its content; refusing to use it is the only safe
    option.
    """


class BundleCatalogQueryError(ProtectedBlobSetError):
    """Working-tree catalog DB checksum matches but the SQLite query
    failed (missing table, missing column, db corruption between mtime
    and read, etc.). Hard failure."""


class RegistryDetailIndexMissingError(ProtectedBlobSetError):
    """An ACTIVE/VALIDATING catalog_releases row points at a
    detail_index_url that does not exist in Supabase storage.

    This is a HARD failure: the registry promises blob protection at
    a path that doesn't exist, which means the row is inconsistent.
    Operator must either upload the missing index OR retire the row.

    Per ADR-0001 P3.5 sign-off: do NOT silently skip — a missing
    promised path is exactly the failure class the registry was built
    to catch.
    """


class RegistryFetchError(ProtectedBlobSetError):
    """Network/storage error while fetching a registry detail_index from
    Supabase storage (timeout, 500, transient connectivity, etc.).

    Caller (gates.py orchestrator) decides whether to retry the whole
    gate evaluation. No silent retry at this layer."""


class MalformedRegistryRowError(ProtectedBlobSetError):
    """An ACTIVE/VALIDATING catalog_releases row has detail_index_url=NULL
    (cannot compute its hashes). Hard failure — the schema permits NULL
    but P3.5 requires non-null for protected states. Mismatch = operator
    error during backfill or activation."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProtectedBlobSet:
    """Result of compute_protected_blob_set.

    Attributes:
        protected: frozenset of all unique blob hashes that must NOT be
            deleted by orphan cleanup. ``bundled_hashes | dist_hashes``.
        bundled_hashes, dist_hashes: per-source unique hash sets.
        bundled_count, dist_count: total entries (with duplicates) per side.
            Always >= the corresponding hash-set size.
        union_count, intersection_count: derived metrics for audit log.
        bundled_version, dist_version: db_version of each side. ``bundled_version``
            is None when degenerate; ``dist_version`` is always present (dist
            is required for the function to return at all).
        bundled_commit_sha: full SHA of the branch HEAD on the bundled side.
            None when degenerate.
        degenerate: True when the bundled side could not be loaded; in that
            case ``protected == dist_hashes`` only and the gating layer
            (P1.5/P1.6) MUST reject this for --execute.
        degenerate_reason: human-readable explanation when ``degenerate``
            is True; None otherwise. Surfaced in the gate's failure message.
    """

    protected: frozenset
    bundled_hashes: frozenset
    dist_hashes: frozenset
    bundled_count: int
    dist_count: int
    union_count: int
    intersection_count: int
    bundled_version: Optional[str]
    dist_version: str
    bundled_commit_sha: Optional[str]
    degenerate: bool
    degenerate_reason: Optional[str] = None
    # --- P3.5: registry-backed protection (additive third source) -------
    # Defaults preserve P1.4-only construction in existing tests and any
    # caller that does not yet pass a Supabase client.
    registry_hashes: frozenset = field(default_factory=frozenset)
    registry_count: int = 0                          # total entries (with dup)
    registry_versions: tuple[str, ...] = ()          # db_versions contributing


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    """Stream-hash a file with SHA256. Bounded memory regardless of file size."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _query_blob_hashes_from_catalog(catalog_path: Path) -> Tuple[frozenset, int]:
    """Query the bundled catalog for all non-null detail_blob_sha256 values.

    Returns:
        (frozenset of unique hashes, total row count including duplicates)
    """
    try:
        conn = sqlite3.connect(str(catalog_path))
    except sqlite3.Error as e:
        raise BundleCatalogQueryError(
            f"Could not open bundled catalog DB: {catalog_path}: {e}"
        ) from e
    try:
        try:
            cursor = conn.execute(
                "SELECT detail_blob_sha256 FROM products_core "
                "WHERE detail_blob_sha256 IS NOT NULL "
                "  AND detail_blob_sha256 != ''"
            )
            rows = cursor.fetchall()
        except sqlite3.Error as e:
            raise BundleCatalogQueryError(
                f"Could not query products_core.detail_blob_sha256 "
                f"in {catalog_path}: {e}"
            ) from e
    finally:
        conn.close()

    hashes = [row[0] for row in rows if isinstance(row[0], str) and row[0]]
    return frozenset(hashes), len(hashes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_protected_blob_set(
    flutter_repo_path: Union[Path, str],
    dist_dir: Union[Path, str],
    *,
    branch: str = DEFAULT_BRANCH,
    bundled_manifest_path: str = DEFAULT_MANIFEST_PATH,
    bundled_catalog_path: str = DEFAULT_BUNDLED_CATALOG_PATH,
    dist_manifest_filename: str = DEFAULT_DIST_MANIFEST_FILENAME,
    dist_index_filename: str = DEFAULT_DIST_INDEX_FILENAME,
    # P3.5: registry side — additive, opt-in via supabase_client
    supabase_client=None,
    registry_bucket: str = DEFAULT_REGISTRY_BUCKET,
    registry_table: Optional[str] = None,
) -> ProtectedBlobSet:
    """Compute the bundled∪dist∪registry protected blob set.

    Args:
        flutter_repo_path: filesystem path to the Flutter repo root.
        dist_dir: filesystem path to the freshly-built ``dist/`` directory.
        branch: Flutter branch to read bundled manifest from. Default ``"main"``.
        bundled_manifest_path: path within Flutter repo (relative).
        bundled_catalog_path: path within Flutter repo (relative). Read from
            working tree, verified against committed manifest's ``checksum_sha256``.
        dist_manifest_filename / dist_index_filename: filenames within ``dist_dir``.
        supabase_client: P3.5 — when provided, the function ALSO fetches every
            catalog_releases row in state ∈ {ACTIVE, VALIDATING}, downloads its
            detail_index_url, validates it, and unions its hashes into the
            protected set. When None, behaves exactly as P1.4 (bundled∪dist only).
        registry_bucket: Supabase storage bucket holding detail_index files.
            Default ``pharmaguide``.
        registry_table: catalog_releases table name. Defaults to the value
            registry.DEFAULT_TABLE — kept as a parameter for testability.

    Returns:
        ``ProtectedBlobSet`` with full bundled∪dist∪registry union when bundled
        and registry sides are loadable; ``degenerate=True`` (and a populated
        ``degenerate_reason``) when the bundled side is absent. The registry
        side is NEVER degenerate — empty registry means zero additional
        protection but does not raise.

    Raises:
        IndexValidationError: dist's OR a registry row's detail_index is missing or malformed.
        ProtectedBlobSetError: dist db_version unknown.
        MalformedBundleManifestError: bundled manifest exists but is broken
            (data corruption, not absence — hard fail).
        MalformedBundleCatalogError: working-tree catalog SHA256 mismatch
            with committed manifest checksum (LFS pointer, local edits, or
            stale checkout — hard fail).
        BundleCatalogQueryError: SQLite open or query failed despite checksum
            matching — hard fail.
        RegistryDetailIndexMissingError: an ACTIVE/VALIDATING row promises
            a detail_index_url that does not exist in storage — hard fail.
        RegistryFetchError: network/storage error fetching a registry index
            — hard fail (no silent retry at this layer).
        MalformedRegistryRowError: an ACTIVE/VALIDATING row has
            detail_index_url=NULL — hard fail (operator error).
    """
    flutter_repo_path = Path(flutter_repo_path)
    dist_dir = Path(dist_dir)

    # --- Step 1: read dist (REQUIRED — fail closed on any error) ---------
    dist_index_path = dist_dir / dist_index_filename
    dist_manifest_path = dist_dir / dist_manifest_filename

    dist_validated = validate_detail_index(dist_index_path)  # raises on any issue

    # Resolve dist db_version: prefer dist export_manifest, fall back to
    # _meta.db_version inside the index if the manifest doesn't carry it.
    dist_version: Optional[str] = dist_validated.db_version
    if dist_manifest_path.exists():
        try:
            with open(dist_manifest_path) as f:
                dist_manifest = json.load(f)
            mv = dist_manifest.get("db_version")
            if isinstance(mv, str) and mv:
                dist_version = mv
        except (json.JSONDecodeError, ValueError, OSError):
            # If dist manifest is malformed but the index is fine, we keep
            # going with whatever the index gave us. If neither has a version,
            # we raise below.
            pass

    if not dist_version:
        raise ProtectedBlobSetError(
            f"Dist db_version unknown — neither {dist_manifest_path} nor "
            f"{dist_index_path}'s _meta block carried a db_version. "
            "Cannot compute protected set without identifying the dist version."
        )

    dist_hashes = dist_validated.blob_hashes
    dist_count = dist_validated.count

    # --- Step 2: try to read bundled (degenerate-tolerant for absence) ---
    degenerate = False
    degenerate_reason: Optional[str] = None
    bundled_hashes: frozenset = frozenset()
    bundled_count = 0
    bundled_version: Optional[str] = None
    bundled_commit_sha: Optional[str] = None

    snapshot = None
    try:
        snapshot = read_flutter_bundle_manifest(
            flutter_repo_path,
            branch=branch,
            manifest_path=bundled_manifest_path,
        )
    except (FlutterRepoNotFoundError, BranchNotFoundError, BundleManifestNotFoundError) as e:
        degenerate = True
        degenerate_reason = (
            f"bundled manifest unavailable: {type(e).__name__}: {e}"
        )
    # MalformedBundleManifestError propagates — data corruption is hard fail.

    if snapshot is not None:
        bundled_version = snapshot.db_version
        bundled_commit_sha = snapshot.commit_sha
        expected_checksum = snapshot.db_checksum_sha256

        if not expected_checksum:
            # Manifest committed but no checksum field → can't verify
            # working-tree DB → degenerate (not corruption — operator may
            # be using an older bundle format).
            degenerate = True
            degenerate_reason = (
                f"bundled manifest at {bundled_manifest_path!r} on "
                f"branch {branch!r} is missing the 'checksum_sha256' field; "
                "cannot verify working-tree catalog DB safely. "
                "P1.5/P1.6 will reject this for --execute."
            )
            bundled_version = None
            bundled_commit_sha = None
        else:
            wt_catalog = flutter_repo_path / bundled_catalog_path
            if not wt_catalog.exists():
                degenerate = True
                degenerate_reason = (
                    f"bundled catalog DB not found in working tree at "
                    f"{wt_catalog}. Run `git lfs pull` (or restore the file) "
                    "before retrying. P1.5/P1.6 will reject this for --execute."
                )
                bundled_version = None
                bundled_commit_sha = None
            else:
                actual_checksum = _sha256_file(wt_catalog)
                if actual_checksum != expected_checksum:
                    raise MalformedBundleCatalogError(
                        "Working-tree catalog DB SHA256 does not match "
                        "committed manifest checksum.\n"
                        f"  catalog file:    {wt_catalog}\n"
                        f"  actual sha256:   {actual_checksum}\n"
                        f"  expected sha256: {expected_checksum}\n"
                        f"  branch:          {branch}\n"
                        f"  commit:          {bundled_commit_sha}\n"
                        "\n"
                        "Common causes:\n"
                        "  - LFS pointer: working-tree file is the Git LFS "
                        "pointer text, not the actual SQLite content. Run\n"
                        "    `git lfs pull` to download the real file.\n"
                        "  - Local modifications: catalog DB was edited "
                        "without a re-bundle.\n"
                        "  - Stale checkout: working tree is on a different "
                        f"branch than the one we read from ({branch!r}).\n"
                    )
                # Checksum verified — safe to query SQLite content.
                bundled_hashes, bundled_count = _query_blob_hashes_from_catalog(wt_catalog)

    # --- Step 3: registry-side fetch (P3.5; opt-in via supabase_client) --
    registry_hashes: frozenset = frozenset()
    registry_count = 0
    registry_versions: tuple[str, ...] = ()
    if supabase_client is not None:
        registry_hashes, registry_count, registry_versions = (
            _fetch_registry_blob_hashes(
                supabase_client,
                bucket=registry_bucket,
                table=registry_table,
            )
        )

    # --- Step 4: compute union (bundled ∪ dist ∪ registry) ---------------
    protected = bundled_hashes | dist_hashes | registry_hashes

    return ProtectedBlobSet(
        protected=protected,
        bundled_hashes=bundled_hashes,
        dist_hashes=dist_hashes,
        bundled_count=bundled_count,
        dist_count=dist_count,
        union_count=len(protected),
        intersection_count=len(bundled_hashes & dist_hashes),
        bundled_version=bundled_version,
        dist_version=dist_version,
        bundled_commit_sha=bundled_commit_sha,
        degenerate=degenerate,
        degenerate_reason=degenerate_reason,
        registry_hashes=registry_hashes,
        registry_count=registry_count,
        registry_versions=registry_versions,
    )


# ---------------------------------------------------------------------------
# P3.5 — registry-backed blob hash fetch
# ---------------------------------------------------------------------------


def _fetch_registry_blob_hashes(
    client,
    *,
    bucket: str,
    table: Optional[str] = None,
) -> Tuple[frozenset, int, Tuple[str, ...]]:
    """Fetch every ACTIVE+VALIDATING registry row, download its detail_index,
    validate it, and union the hashes.

    Per ADR-0001 P3.5 sign-off:
      - ACTIVE ∪ VALIDATING are protected. PENDING and RETIRED are excluded.
      - Missing detail_index_url on a protected row -> hard fail.
      - Index path missing in storage -> hard fail.
      - Malformed index -> hard fail (propagates IndexValidationError).
      - Network/fetch error -> hard fail (raises RegistryFetchError).
      - Sequential fetches; concurrency is a future optimization.

    Returns:
        (frozenset of unique hashes, total entry count with duplicates,
         tuple of db_versions that contributed in order encountered).
    """
    # Local import: registry depends on nothing from this module so this
    # is one-way; the import is at call time to keep module import cheap.
    from .registry import (
        DEFAULT_TABLE as REGISTRY_DEFAULT_TABLE,
        ReleaseState,
        list_releases_by_state,
    )

    table_name = table or REGISTRY_DEFAULT_TABLE
    actives = list_releases_by_state(client, ReleaseState.ACTIVE, table=table_name)
    validatings = list_releases_by_state(client, ReleaseState.VALIDATING, table=table_name)
    protected_rows = list(actives) + list(validatings)

    all_hashes: set[str] = set()
    total_count = 0
    versions: list[str] = []

    for release in protected_rows:
        if not release.detail_index_url:
            raise MalformedRegistryRowError(
                f"catalog_releases row db_version={release.db_version!r} is in "
                f"state {release.state.value} but detail_index_url is NULL. "
                f"P3.5 requires non-null detail_index_url for ACTIVE/VALIDATING "
                f"rows. Either set the URL or retire the row before cleanup."
            )

        index_bytes = _fetch_index_from_storage(
            client,
            bucket=bucket,
            storage_path=release.detail_index_url,
            db_version=release.db_version,
        )

        # validate_detail_index works from a filesystem path; write to a
        # tempfile and unlink after parsing. The validator is responsible
        # for rejecting malformed JSON / structure / hashes (hard fail).
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".json", delete=False,
        ) as tmp:
            tmp.write(index_bytes)
            tmp_path = Path(tmp.name)
        try:
            validated = validate_detail_index(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        all_hashes.update(validated.blob_hashes)
        total_count += validated.count
        versions.append(release.db_version)

    return frozenset(all_hashes), total_count, tuple(versions)


def _fetch_index_from_storage(
    client,
    *,
    bucket: str,
    storage_path: str,
    db_version: str,
) -> bytes:
    """Download a registry detail_index from Supabase storage.

    Existence is verified via list() first so the error path for a
    missing object is clean (no reliance on supabase-py's specific
    download-failure exception types, which vary across client versions).

    Raises:
        RegistryDetailIndexMissingError: object does not exist in storage.
        RegistryFetchError: list or download failed for any other reason.
    """
    if "/" in storage_path:
        parent, basename = storage_path.rsplit("/", 1)
    else:
        parent, basename = "", storage_path

    try:
        items = client.storage.from_(bucket).list(
            path=parent,
            options={"limit": 1000, "offset": 0},
        )
    except Exception as exc:  # noqa: BLE001
        raise RegistryFetchError(
            f"Failed to list bucket={bucket!r} path={parent!r} while looking "
            f"up registry detail_index for db_version={db_version!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    items = items or []
    found = any(
        isinstance(i, dict) and i.get("name") == basename for i in items
    )
    if not found:
        raise RegistryDetailIndexMissingError(
            f"catalog_releases row db_version={db_version!r} promises "
            f"detail_index at {bucket}/{storage_path} but the object does NOT "
            f"exist in storage. Either upload the missing index or retire the "
            f"row before cleanup can run."
        )

    try:
        return client.storage.from_(bucket).download(storage_path)
    except Exception as exc:  # noqa: BLE001
        raise RegistryFetchError(
            f"Failed to download {bucket}/{storage_path} for db_version="
            f"{db_version!r}: {type(exc).__name__}: {exc}"
        ) from exc
