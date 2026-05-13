"""Read-only storage audit for the Supabase ``pharmaguide`` bucket.

This module is **strictly read-only**. It uses ``storage.from_(bucket).list(...)``
calls only — never ``download``, ``copy``, ``remove``, or ``upload``. It is
safe to run any time, on any environment, without touching state.

What it answers
===============
The audit produces a ``StorageAuditReport`` that quantifies:

  - **Total bucket size** (bytes + object count) and the breakdown by
    top-level prefix.
  - **Active / protected**: blobs in ``shared/details/sha256/`` that
    are referenced by the Flutter-bundled catalog AND/OR by the local
    dist's detail_index. (Same ``bundled∪dist`` set the P1.4 protection
    layer would compute.)
  - **Orphans**: blobs in ``shared/details/sha256/`` NOT in
    bundled∪dist. These are the targets of future cleanup.
  - **Already quarantined**: under ``shared/quarantine/{date}/``;
    eligible for sweep after their TTL.
  - **Per-version legacy directories**: ``pharmaguide/v{version}/`` —
    older catalog/manifest snapshots from earlier release cycles.
  - **Cleanup projections** (no action taken):
      A. Net effect of quarantining all current orphans: ZERO immediate
         change (move-not-delete) but flips them to TTL-eligible.
      B. Net effect of A + 30d quarantine sweep: −orphans bytes.
      C. Net effect of B + per-version-dir hard delete: also −per-version bytes.
      D. Combined minimum after full cleanup.

What this is NOT
================
Not a cleanup tool. Not a quarantine tool. Not a sweeper. Just the
inventory + projections needed for an operator to make an informed
storage-pressure decision.

Public API
==========
    run_storage_audit(client, *, flutter_repo_path, dist_dir,
                       bucket=DEFAULT_BUCKET, ...)
        -> StorageAuditReport

    StorageAuditReport
        .text_report()  -> str       — operator-facing summary
        .to_dict()      -> dict      — machine-readable for tooling
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .quarantine import (
    ACTIVE_PREFIX,
    DEFAULT_BUCKET,
    QUARANTINE_PREFIX,
    list_quarantine_dates,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VERSION_DIR_RE = re.compile(r"^v\d{4}\.\d{2}\.\d{2}\.\d+$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

DEFAULT_ORPHAN_SAMPLE_SIZE = 10

# Free-plan reference numbers (operator can pass overrides via the CLI).
SUPABASE_FREE_TIER_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrefixStats:
    """Recursive count + byte sum for everything under a storage prefix."""

    prefix: str
    object_count: int
    total_bytes: int
    size_unknown_count: int = 0   # objects whose size couldn't be read


@dataclass(frozen=True)
class StorageAuditReport:
    bucket: str

    # Top-level breakdown
    by_top_prefix: Dict[str, PrefixStats]
    bucket_total_bytes: int
    bucket_total_objects: int

    # shared/details/sha256/ — the active blob storage
    details_total_objects: int
    details_total_bytes: int

    # Cross-reference inputs
    bundled_db_version: Optional[str]
    dist_db_version: Optional[str]
    bundled_hash_count: int                # hashes the bundled catalog references
    dist_hash_count: int                   # hashes dist's detail_index references
    union_hash_count: int                  # bundled ∪ dist (unique)

    # Storage cross-reference (in shared/details that ALSO are bundled / dist / union)
    bundled_in_storage_count: int
    bundled_in_storage_bytes: int
    dist_in_storage_count: int
    dist_in_storage_bytes: int
    union_in_storage_count: int
    union_in_storage_bytes: int

    # Orphans (in shared/details, NOT in bundled∪dist)
    orphan_count: int
    orphan_total_bytes: int
    orphan_sample_hashes: List[str]

    # Bundled / dist entries the catalog references but storage is missing
    bundled_missing_from_storage_count: int
    dist_missing_from_storage_count: int

    # shared/quarantine/{date}/
    quarantine_total_objects: int
    quarantine_total_bytes: int
    quarantine_dates: Dict[str, PrefixStats]

    # pharmaguide/v{version}/ — legacy per-version directories
    per_version_dirs: Dict[str, PrefixStats]
    per_version_total_objects: int
    per_version_total_bytes: int

    # Anything else at the top level (audit-only — surfaces unexpected dirs)
    other_top_prefixes: Dict[str, PrefixStats] = field(default_factory=dict)

    # Reasons the bundled side might be missing (LFS pointer / stale catalog)
    bundled_load_warning: Optional[str] = None

    # ----- projections -----

    def projection_quarantine_orphans_then_sweep(self) -> int:
        """Bytes after: quarantine current orphans (no immediate change),
        then 30-day sweep. End state: orphans gone."""
        return self.bucket_total_bytes - self.orphan_total_bytes

    def projection_delete_per_version_dirs(self) -> int:
        """Bytes after: hard-delete pharmaguide/v{version}/ legacy dirs."""
        return self.bucket_total_bytes - self.per_version_total_bytes

    def projection_full_cleanup(self) -> int:
        """Bytes after: orphan quarantine swept + per-version dirs deleted +
        existing quarantine swept. Minimum achievable without breaking
        bundled/dist consumers."""
        return (
            self.bucket_total_bytes
            - self.orphan_total_bytes
            - self.per_version_total_bytes
            - self.quarantine_total_bytes
        )

    # ----- output formats -----

    def text_report(self, free_tier_bytes: int = SUPABASE_FREE_TIER_BYTES) -> str:
        b = StringBuilder = []  # noqa: N806 (using as alias for clarity)

        def add(line: str = "") -> None:
            b.append(line)

        add("=" * 70)
        add(f"Storage Audit — bucket: {self.bucket}")
        add("=" * 70)
        add()

        # 1. What is using the bytes
        add("─── 1. WHAT IS USING THE BYTES ─────────────────────────────────")
        add(f"  Total in bucket:     {_fmt_bytes(self.bucket_total_bytes)}  "
            f"({self.bucket_total_objects:,} objects)")
        add(f"  Free-plan limit:     {_fmt_bytes(free_tier_bytes)}")
        over = self.bucket_total_bytes - free_tier_bytes
        if over > 0:
            add(f"  OVER LIMIT BY:       {_fmt_bytes(over)}  ⚠")
        else:
            add(f"  Under limit by:      {_fmt_bytes(-over)}")
        add()
        add("  Top-level prefix breakdown (sorted by size):")
        sorted_prefixes = sorted(
            self.by_top_prefix.items(),
            key=lambda kv: kv[1].total_bytes,
            reverse=True,
        )
        for name, stats in sorted_prefixes:
            pct = (stats.total_bytes / self.bucket_total_bytes * 100
                   if self.bucket_total_bytes else 0)
            add(f"    {_fmt_bytes(stats.total_bytes):>12}  "
                f"{stats.object_count:>8,} obj  "
                f"({pct:5.1f}%)  {name}/")
        add()

        # 2. Active / protected
        add("─── 2. ACTIVE / PROTECTED ──────────────────────────────────────")
        if self.bundled_load_warning:
            add(f"  ⚠ Bundled side: {self.bundled_load_warning}")
            add()
        add(f"  Bundled catalog version:  {self.bundled_db_version or '(unknown)'}")
        add(f"  Dist catalog version:     {self.dist_db_version or '(unknown)'}")
        add()
        add(f"  Bundled references:       {self.bundled_hash_count:,} blob hashes")
        add(f"  Dist references:          {self.dist_hash_count:,} blob hashes")
        add(f"  Union (bundled ∪ dist):   {self.union_hash_count:,} unique hashes")
        add()
        add(f"  Bundled blobs IN storage: {self.bundled_in_storage_count:,}  "
            f"({_fmt_bytes(self.bundled_in_storage_bytes)})")
        add(f"  Dist blobs IN storage:    {self.dist_in_storage_count:,}  "
            f"({_fmt_bytes(self.dist_in_storage_bytes)})")
        add(f"  Union blobs IN storage:   {self.union_in_storage_count:,}  "
            f"({_fmt_bytes(self.union_in_storage_bytes)})")
        add()
        if self.bundled_missing_from_storage_count:
            add(f"  ⚠ Bundled refs MISSING from storage: "
                f"{self.bundled_missing_from_storage_count:,}")
            add("    (consumer-side fetches will 404 — exactly the 2026-05-12 mode)")
        if self.dist_missing_from_storage_count:
            add(f"  ⚠ Dist refs MISSING from storage: "
                f"{self.dist_missing_from_storage_count:,}")
            add("    (next release will create them on upload)")
        add()

        # 3. Orphans
        add("─── 3. ORPHANS (in shared/details, NOT bundled∪dist) ───────────")
        add(f"  Count:           {self.orphan_count:,}")
        add(f"  Total bytes:     {_fmt_bytes(self.orphan_total_bytes)}")
        if self.orphan_sample_hashes:
            add(f"  Sample hashes (first {len(self.orphan_sample_hashes)}):")
            for h in self.orphan_sample_hashes:
                add(f"    {h[:16]}…")
        add()

        # 4. Quarantine
        add("─── 4. ALREADY QUARANTINED ─────────────────────────────────────")
        add(f"  Total objects:   {self.quarantine_total_objects:,}")
        add(f"  Total bytes:     {_fmt_bytes(self.quarantine_total_bytes)}")
        if self.quarantine_dates:
            add("  By date (TTL = 30 days from this date):")
            for date_str in sorted(self.quarantine_dates):
                stats = self.quarantine_dates[date_str]
                add(f"    {date_str}  {stats.object_count:>6,} obj  "
                    f"{_fmt_bytes(stats.total_bytes):>10}")
        add()

        # 5. Per-version dirs
        add("─── 5. LEGACY PER-VERSION DIRECTORIES (pharmaguide/v…/) ────────")
        add(f"  Directory count: {len(self.per_version_dirs):,}")
        add(f"  Total objects:   {self.per_version_total_objects:,}")
        add(f"  Total bytes:     {_fmt_bytes(self.per_version_total_bytes)}")
        add("  These are old metadata snapshots; safe to hard-delete after")
        add("  confirming no installed app depends on a specific version.")
        if self.per_version_dirs:
            add("  Per directory:")
            for name in sorted(self.per_version_dirs):
                stats = self.per_version_dirs[name]
                add(f"    {name:<25}  {stats.object_count:>6,} obj  "
                    f"{_fmt_bytes(stats.total_bytes):>10}")
        add()

        # 6. Other top-level
        if self.other_top_prefixes:
            add("─── 6. OTHER TOP-LEVEL PREFIXES (not categorized) ─────────────")
            for name in sorted(self.other_top_prefixes):
                stats = self.other_top_prefixes[name]
                add(f"    {name:<30}  {stats.object_count:>6,} obj  "
                    f"{_fmt_bytes(stats.total_bytes):>10}")
            add()

        # 7. Cleanup projections
        add("─── 7. CLEANUP PROJECTIONS (no action taken) ──────────────────")
        add(f"  Current bucket size:                          "
            f"{_fmt_bytes(self.bucket_total_bytes)}")
        add()
        add("  After P2 quarantine of all current orphans:")
        add(f"    immediate effect:                           "
            f"+0 (move, not delete)")
        add(f"    after 30-day quarantine sweep:              "
            f"{_fmt_bytes(self.projection_quarantine_orphans_then_sweep())}  "
            f"(saves {_fmt_bytes(self.orphan_total_bytes)})")
        add()
        add("  After hard-delete of legacy per-version dirs:")
        add(f"    immediate effect:                           "
            f"{_fmt_bytes(self.projection_delete_per_version_dirs())}  "
            f"(saves {_fmt_bytes(self.per_version_total_bytes)})")
        add()
        add("  Minimum after full cleanup")
        add("  (orphans swept + per-version deleted + existing quarantine swept):")
        full = self.projection_full_cleanup()
        add(f"    {_fmt_bytes(full)}  "
            f"(saves {_fmt_bytes(self.bucket_total_bytes - full)})")
        if free_tier_bytes:
            margin = free_tier_bytes - full
            if margin >= 0:
                add(f"    Margin under free-tier limit:               "
                    f"{_fmt_bytes(margin)}")
            else:
                add(f"    STILL OVER free-tier limit by:              "
                    f"{_fmt_bytes(-margin)}  ⚠")
        add()

        return "\n".join(b)

    def to_dict(self) -> dict:
        return {
            "bucket": self.bucket,
            "totals": {
                "bytes": self.bucket_total_bytes,
                "objects": self.bucket_total_objects,
            },
            "by_top_prefix": {
                name: {"objects": s.object_count, "bytes": s.total_bytes}
                for name, s in self.by_top_prefix.items()
            },
            "details": {
                "total_objects": self.details_total_objects,
                "total_bytes": self.details_total_bytes,
            },
            "bundled": {
                "db_version": self.bundled_db_version,
                "hash_count": self.bundled_hash_count,
                "in_storage_count": self.bundled_in_storage_count,
                "in_storage_bytes": self.bundled_in_storage_bytes,
                "missing_from_storage_count": self.bundled_missing_from_storage_count,
                "load_warning": self.bundled_load_warning,
            },
            "dist": {
                "db_version": self.dist_db_version,
                "hash_count": self.dist_hash_count,
                "in_storage_count": self.dist_in_storage_count,
                "in_storage_bytes": self.dist_in_storage_bytes,
                "missing_from_storage_count": self.dist_missing_from_storage_count,
            },
            "union": {
                "hash_count": self.union_hash_count,
                "in_storage_count": self.union_in_storage_count,
                "in_storage_bytes": self.union_in_storage_bytes,
            },
            "orphans": {
                "count": self.orphan_count,
                "total_bytes": self.orphan_total_bytes,
                "sample_hashes": self.orphan_sample_hashes,
            },
            "quarantine": {
                "total_objects": self.quarantine_total_objects,
                "total_bytes": self.quarantine_total_bytes,
                "by_date": {
                    d: {"objects": s.object_count, "bytes": s.total_bytes}
                    for d, s in self.quarantine_dates.items()
                },
            },
            "per_version_dirs": {
                name: {"objects": s.object_count, "bytes": s.total_bytes}
                for name, s in self.per_version_dirs.items()
            },
            "other_top_prefixes": {
                name: {"objects": s.object_count, "bytes": s.total_bytes}
                for name, s in self.other_top_prefixes.items()
            },
            "projections": {
                "current_bytes": self.bucket_total_bytes,
                "after_orphan_quarantine_sweep_bytes":
                    self.projection_quarantine_orphans_then_sweep(),
                "after_per_version_delete_bytes":
                    self.projection_delete_per_version_dirs(),
                "after_full_cleanup_bytes": self.projection_full_cleanup(),
            },
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_storage_audit(
    client,
    *,
    flutter_repo_path: Path,
    dist_dir: Path,
    bucket: str = DEFAULT_BUCKET,
    bundled_manifest_relpath: str = "assets/db/export_manifest.json",
    bundled_catalog_relpath: str = "assets/db/pharmaguide_core.db",
    dist_index_filename: str = "detail_index.json",
    dist_manifest_filename: str = "export_manifest.json",
    orphan_sample_size: int = DEFAULT_ORPHAN_SAMPLE_SIZE,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> StorageAuditReport:
    """Walk Supabase storage and produce an audit report.

    Read-only. Calls only ``client.storage.from_(bucket).list(...)``.
    """
    flutter_repo_path = Path(flutter_repo_path)
    dist_dir = Path(dist_dir)

    # ---- Step 1: cross-reference catalog hashes -----------------------
    bundled_db_version, bundled_hashes, bundled_load_warning = \
        _load_bundled_hashes(flutter_repo_path, bundled_manifest_relpath,
                             bundled_catalog_relpath)
    dist_db_version, dist_hashes = \
        _load_dist_hashes(dist_dir, dist_index_filename, dist_manifest_filename)

    union_hashes = bundled_hashes | dist_hashes

    # ---- Step 2: walk top-level + per-version dirs --------------------
    by_top_prefix: Dict[str, PrefixStats] = {}
    per_version_dirs: Dict[str, PrefixStats] = {}
    other_top_prefixes: Dict[str, PrefixStats] = {}

    top_items = _list_paginated(client, bucket, "")
    known_top = {"shared", "pharmaguide", "user_avatars", "product_images"}

    for item in top_items:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name:
            continue

        size = _item_size(item)
        if size is not None:
            # File at root level — bucket pollution, account for it
            other_top_prefixes[name] = PrefixStats(
                prefix=name, object_count=1, total_bytes=size,
            )
            continue

        # Directory — walk recursively
        if _VERSION_DIR_RE.match(name):
            stats = _walk_prefix(client, bucket, name,
                                 progress_callback=progress_callback)
            per_version_dirs[name] = stats
            by_top_prefix[name] = stats
            continue

        stats = _walk_prefix(client, bucket, name,
                             progress_callback=progress_callback)
        by_top_prefix[name] = stats
        if name not in known_top:
            other_top_prefixes[name] = stats

    bucket_total_bytes = sum(s.total_bytes for s in by_top_prefix.values())
    bucket_total_objects = sum(s.object_count for s in by_top_prefix.values())

    # ---- Step 3: enumerate shared/details/sha256/ blobs ---------------
    detail_blobs = _enumerate_detail_blobs(client, bucket, ACTIVE_PREFIX)

    details_total_objects = len(detail_blobs)
    details_total_bytes = sum(s for s in detail_blobs.values() if s is not None)

    bundled_in_storage = {
        h: s for h, s in detail_blobs.items() if h in bundled_hashes
    }
    dist_in_storage = {h: s for h, s in detail_blobs.items() if h in dist_hashes}
    union_in_storage = {h: s for h, s in detail_blobs.items() if h in union_hashes}
    orphan_in_storage = {
        h: s for h, s in detail_blobs.items() if h not in union_hashes
    }

    bundled_missing = len(bundled_hashes) - len(bundled_in_storage)
    dist_missing = len(dist_hashes) - len(dist_in_storage)

    sample_orphans = sorted(orphan_in_storage.keys())[:orphan_sample_size]

    # ---- Step 4: enumerate quarantine ---------------------------------
    quarantine_dates_stats: Dict[str, PrefixStats] = {}
    for date_str in list_quarantine_dates(client, bucket=bucket):
        stats = _walk_prefix(
            client, bucket, f"{QUARANTINE_PREFIX}/{date_str}",
            progress_callback=progress_callback,
        )
        quarantine_dates_stats[date_str] = stats

    quarantine_total_objects = sum(
        s.object_count for s in quarantine_dates_stats.values()
    )
    quarantine_total_bytes = sum(
        s.total_bytes for s in quarantine_dates_stats.values()
    )

    per_version_total_bytes = sum(s.total_bytes for s in per_version_dirs.values())
    per_version_total_objects = sum(
        s.object_count for s in per_version_dirs.values()
    )

    return StorageAuditReport(
        bucket=bucket,
        by_top_prefix=by_top_prefix,
        bucket_total_bytes=bucket_total_bytes,
        bucket_total_objects=bucket_total_objects,
        details_total_objects=details_total_objects,
        details_total_bytes=details_total_bytes,
        bundled_db_version=bundled_db_version,
        dist_db_version=dist_db_version,
        bundled_hash_count=len(bundled_hashes),
        dist_hash_count=len(dist_hashes),
        union_hash_count=len(union_hashes),
        bundled_in_storage_count=len(bundled_in_storage),
        bundled_in_storage_bytes=sum(
            s for s in bundled_in_storage.values() if s is not None
        ),
        dist_in_storage_count=len(dist_in_storage),
        dist_in_storage_bytes=sum(
            s for s in dist_in_storage.values() if s is not None
        ),
        union_in_storage_count=len(union_in_storage),
        union_in_storage_bytes=sum(
            s for s in union_in_storage.values() if s is not None
        ),
        orphan_count=len(orphan_in_storage),
        orphan_total_bytes=sum(
            s for s in orphan_in_storage.values() if s is not None
        ),
        orphan_sample_hashes=sample_orphans,
        bundled_missing_from_storage_count=bundled_missing,
        dist_missing_from_storage_count=dist_missing,
        quarantine_total_objects=quarantine_total_objects,
        quarantine_total_bytes=quarantine_total_bytes,
        quarantine_dates=quarantine_dates_stats,
        per_version_dirs=per_version_dirs,
        per_version_total_objects=per_version_total_objects,
        per_version_total_bytes=per_version_total_bytes,
        other_top_prefixes=other_top_prefixes,
        bundled_load_warning=bundled_load_warning,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _list_paginated(client, bucket: str, prefix: str) -> List[dict]:
    """List ALL items under a prefix, paginating past the 1000-item limit."""
    items: List[dict] = []
    offset = 0
    page_size = 1000
    while True:
        try:
            page = client.storage.from_(bucket).list(
                path=prefix,
                options={"limit": page_size, "offset": offset},
            )
        except Exception:  # noqa: BLE001 — list errors → treat as empty
            break
        if not page:
            break
        items.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return items


def _item_size(item: dict) -> Optional[int]:
    """Extract size from a Supabase list item. Returns None if not available
    (typically directories, or older API responses without metadata)."""
    if not isinstance(item, dict):
        return None
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        size = metadata.get("size")
        if isinstance(size, int):
            return size
    fallback = item.get("size")
    if isinstance(fallback, int):
        return fallback
    return None


def _walk_prefix(
    client,
    bucket: str,
    prefix: str,
    *,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> PrefixStats:
    """Recursively walk a storage prefix; return aggregate stats."""
    object_count = 0
    total_bytes = 0
    size_unknown = 0

    items = _list_paginated(client, bucket, prefix)
    for item in items:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name:
            continue

        size = _item_size(item)
        if size is not None:
            object_count += 1
            total_bytes += size
        else:
            sub = _walk_prefix(client, bucket, f"{prefix}/{name}",
                               progress_callback=progress_callback)
            object_count += sub.object_count
            total_bytes += sub.total_bytes
            size_unknown += sub.size_unknown_count

    if progress_callback is not None:
        progress_callback(prefix, object_count)

    return PrefixStats(
        prefix=prefix,
        object_count=object_count,
        total_bytes=total_bytes,
        size_unknown_count=size_unknown,
    )


def _enumerate_detail_blobs(
    client, bucket: str, prefix: str = ACTIVE_PREFIX,
) -> Dict[str, Optional[int]]:
    """Walk shared/details/sha256/{shard}/{hash}.json — return hash -> size."""
    blobs: Dict[str, Optional[int]] = {}
    shards = _list_paginated(client, bucket, prefix)
    for shard_item in shards:
        shard_name = (shard_item or {}).get("name")
        if not isinstance(shard_name, str) or len(shard_name) != 2:
            continue
        for blob_item in _list_paginated(client, bucket, f"{prefix}/{shard_name}"):
            leaf = (blob_item or {}).get("name")
            if not isinstance(leaf, str) or not leaf.endswith(".json"):
                continue
            blob_hash = leaf[:-5]
            if not _HASH_RE.match(blob_hash):
                continue
            blobs[blob_hash] = _item_size(blob_item)
    return blobs


def _load_bundled_hashes(
    flutter_repo_path: Path,
    manifest_relpath: str,
    catalog_relpath: str,
) -> Tuple[Optional[str], frozenset, Optional[str]]:
    """Load bundled catalog hashes from the Flutter repo's working tree.

    Returns ``(db_version, hashes, warning_message_or_None)``. On any
    failure to load (LFS pointer / missing file / SQLite error) we
    return what we have plus a human-readable warning instead of raising
    — the audit should still produce useful output.
    """
    import sqlite3 as _sqlite3

    manifest_path = flutter_repo_path / manifest_relpath
    catalog_path = flutter_repo_path / catalog_relpath

    db_version: Optional[str] = None
    if manifest_path.exists():
        try:
            db_version = json.loads(manifest_path.read_text()).get("db_version")
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    if not catalog_path.exists():
        return db_version, frozenset(), (
            f"bundled catalog not found at {catalog_path}"
        )

    # Quick LFS-pointer detection: if file is < 200 bytes and starts with
    # "version https://git-lfs.github.com/", it's the pointer.
    try:
        head = catalog_path.read_bytes()[:200]
        if head.startswith(b"version https://git-lfs.github.com/"):
            return db_version, frozenset(), (
                "bundled catalog is a Git LFS pointer (run `git lfs pull`)"
            )
    except OSError:
        pass

    try:
        conn = _sqlite3.connect(str(catalog_path))
        try:
            cur = conn.execute(
                "SELECT detail_blob_sha256 FROM products_core "
                "WHERE detail_blob_sha256 IS NOT NULL "
                "  AND detail_blob_sha256 != ''"
            )
            hashes = frozenset(
                row[0] for row in cur.fetchall()
                if isinstance(row[0], str) and _HASH_RE.match(row[0])
            )
        finally:
            conn.close()
    except _sqlite3.Error as exc:
        return db_version, frozenset(), f"could not query bundled catalog: {exc}"

    return db_version, hashes, None


def _load_dist_hashes(
    dist_dir: Path,
    dist_index_filename: str,
    dist_manifest_filename: str,
) -> Tuple[Optional[str], frozenset]:
    """Load dist's detail_index and return (db_version, hashes)."""
    dist_dir = Path(dist_dir)
    db_version: Optional[str] = None

    manifest_path = dist_dir / dist_manifest_filename
    if manifest_path.exists():
        try:
            db_version = json.loads(manifest_path.read_text()).get("db_version")
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    index_path = dist_dir / dist_index_filename
    if not index_path.exists():
        return db_version, frozenset()

    try:
        index = json.loads(index_path.read_text())
    except (json.JSONDecodeError, ValueError, OSError):
        return db_version, frozenset()

    if not isinstance(index, dict):
        return db_version, frozenset()

    hashes: set = set()
    for key, entry in index.items():
        if key.startswith("_"):
            continue
        if not isinstance(entry, dict):
            continue
        h = entry.get("blob_sha256")
        if isinstance(h, str) and _HASH_RE.match(h):
            hashes.add(h)
            continue
        # Fallback: parse from storage_path
        sp = entry.get("storage_path")
        if isinstance(sp, str):
            leaf = sp.rsplit("/", 1)[-1]
            if leaf.endswith(".json"):
                candidate = leaf[:-5]
                if _HASH_RE.match(candidate):
                    hashes.add(candidate)

    return db_version, frozenset(hashes)


def _fmt_bytes(n: int) -> str:
    """Human-readable byte count (KiB/MiB/GiB)."""
    if n is None:
        return "-"
    sign = "-" if n < 0 else ""
    n = abs(n)
    for unit, suffix in [(1024**3, "GiB"), (1024**2, "MiB"), (1024, "KiB")]:
        if n >= unit:
            return f"{sign}{n / unit:.2f} {suffix}"
    return f"{sign}{n} B"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv=None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Read-only Supabase storage audit (ADR-0001 P3 prereq).",
    )
    parser.add_argument("--flutter-repo", required=True, type=Path,
                        help="Path to Flutter repo root.")
    parser.add_argument("--dist-dir", required=True, type=Path,
                        help="Path to local dist/ directory.")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET,
                        help=f"Supabase bucket (default {DEFAULT_BUCKET}).")
    parser.add_argument("--orphan-sample-size", type=int,
                        default=DEFAULT_ORPHAN_SAMPLE_SIZE,
                        help="How many orphan hashes to print as a sample.")
    parser.add_argument("--json", action="store_true",
                        help="Output structured JSON instead of text.")
    parser.add_argument("--progress", action="store_true",
                        help="Print per-prefix progress to stderr.")
    args = parser.parse_args(argv)

    # Lazy import — release_safety.storage_audit doesn't depend on
    # supabase_client, but the CLI does.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from supabase_client import get_supabase_client  # noqa: E402

    try:
        client = get_supabase_client()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect to Supabase: {exc}", file=sys.stderr)
        return 1

    progress_cb = None
    if args.progress:
        def progress_cb(prefix, count):  # noqa: F811
            print(f"  …walked {prefix}: {count:,} objects", file=sys.stderr)

    report = run_storage_audit(
        client,
        flutter_repo_path=args.flutter_repo,
        dist_dir=args.dist_dir,
        bucket=args.bucket,
        orphan_sample_size=args.orphan_sample_size,
        progress_callback=progress_cb,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.text_report())

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
