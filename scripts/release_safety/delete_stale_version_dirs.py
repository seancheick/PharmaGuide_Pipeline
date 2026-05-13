"""Delete stale ``pharmaguide/v{version}/`` directories whose db_version
is NOT in the ``export_manifest`` table.

Bucket-2-only cleanup tool (per the storage audit classification). It
NEVER touches:
  - ``shared/details/sha256/`` blobs (active or orphan)
  - product images
  - any ``v{version}/`` dir that has a row in ``export_manifest``
  - the current ``is_current=true`` row's dir
  - any other bucket

Safety chain (every guard must pass before any deletion happens):

  1. Default mode is dry-run; ``--execute`` required for real work.
  2. ``--expected-count`` AND ``--expected-bytes`` REQUIRED with --execute,
     and BOTH must equal the actual computed totals exactly.
  3. Each candidate version is checked against the manifest one final
     time inside ``execute_delete_plan`` (defensive — manifest could
     change between the dry-run and execute call).
  4. Acquires the pipeline release lock (HR-12) before any state-mutating
     storage call.
  5. Per-object delete failures are counted and reported; the cleanup
     CONTINUES across remaining objects (no half-deleted dirs left
     un-noticed).
  6. Audit log records every decision: plan_computed, lock_acquired,
     version_dir_deleted, lock_released, complete.

Public API
==========
    compute_delete_plan(client, *, bucket=DEFAULT_BUCKET,
                        manifest_table="export_manifest")
        -> DeletePlan

    execute_delete_plan(client, plan, *, expected_count, expected_bytes,
                        bucket=DEFAULT_BUCKET,
                        audit_log=None, lock_path=None)
        -> DeleteResult

CLI
===
    python -m release_safety.delete_stale_version_dirs
        # dry-run by default; prints exact plan + totals

    python -m release_safety.delete_stale_version_dirs \\
        --execute --expected-count 2392 --expected-bytes 540369024
        # after operator-confirmed plan
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from .audit_log import AuditLog, make_audit_log
from .lock import (
    CorruptLockError,
    LockContentionError,
    StaleLockError,
    acquire_release_lock,
)
from .quarantine import DEFAULT_BUCKET

# _list_paginated logic re-implemented below — the storage-audit /
# quarantine modules don't export an internal listing helper, and
# duplicating ~10 lines is cleaner than tangling cross-module imports
# of private functions.

DEFAULT_MANIFEST_TABLE = "export_manifest"
_VERSION_DIR_RE = re.compile(r"^v\d{4}\.\d{2}\.\d{2}\..+$")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateVersion:
    """A pharmaguide/v{version}/ directory eligible for deletion.

    Eligibility means: the db_version was NOT found in the manifest
    table at plan-computation time. Final check happens again in
    ``execute_delete_plan`` (defensive).
    """

    db_version: str            # e.g. "2026.03.30.013948"
    dir_path: str              # "v2026.03.30.013948"
    object_count: int
    total_bytes: int
    objects: Tuple[Tuple[str, int], ...]   # (full_path, size_bytes) pairs


@dataclass(frozen=True)
class DeletePlan:
    """Output of compute_delete_plan. Read-only — no side effects."""

    candidates: Tuple[CandidateVersion, ...]
    excluded_versions_in_manifest: Tuple[str, ...]   # for transparency
    bucket: str
    manifest_table: str

    @property
    def total_versions(self) -> int:
        return len(self.candidates)

    @property
    def total_objects(self) -> int:
        return sum(c.object_count for c in self.candidates)

    @property
    def total_bytes(self) -> int:
        return sum(c.total_bytes for c in self.candidates)


@dataclass(frozen=True)
class DeleteResult:
    """Output of execute_delete_plan. Captures what actually happened."""

    plan: DeletePlan
    deleted_versions: Tuple[str, ...]
    deleted_objects_count: int
    deleted_bytes: int
    failed_objects: Tuple[Tuple[str, str], ...]   # (path, error)
    audit_log_path: Optional[Path]

    @property
    def passed(self) -> bool:
        return len(self.failed_objects) == 0


class ExpectedCountMismatch(Exception):
    """--expected-count or --expected-bytes did not match the plan."""


class ManifestRaceConditionError(Exception):
    """A version that was a candidate at plan time appeared in the
    manifest at execute time. Indicates a concurrent release; refuse."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_delete_plan(
    client,
    *,
    bucket: str = DEFAULT_BUCKET,
    manifest_table: str = DEFAULT_MANIFEST_TABLE,
) -> DeletePlan:
    """Build the deletion plan. STRICTLY READ-ONLY.

    Walks ``pharmaguide/v.../`` directories in storage, queries the
    ``export_manifest`` table for known db_versions, and returns the
    set difference (storage v-dirs whose db_version is NOT in manifest).

    For each candidate, lists every object inside so the executor has
    the exact file list — no further enumeration happens at execute
    time.
    """
    manifest_versions = _fetch_manifest_versions(client, manifest_table)

    storage_v_dirs = _list_storage_v_dirs(client, bucket)

    candidates: List[CandidateVersion] = []
    excluded: List[str] = []

    for v_dir_name in storage_v_dirs:
        # v_dir_name is "v2026.03.17.1" — strip the leading "v" for
        # comparison with manifest db_version.
        db_version = v_dir_name[1:] if v_dir_name.startswith("v") else v_dir_name
        if db_version in manifest_versions:
            excluded.append(db_version)
            continue
        # Walk the v-dir to enumerate every object + sum bytes.
        path_size_pairs = _enumerate_dir_objects(client, bucket, v_dir_name)
        total_bytes = sum(size for _path, size in path_size_pairs)
        candidates.append(CandidateVersion(
            db_version=db_version,
            dir_path=v_dir_name,
            object_count=len(path_size_pairs),
            total_bytes=total_bytes,
            objects=tuple(path_size_pairs),
        ))

    # Sort for deterministic output (db_version is lexically sortable).
    candidates.sort(key=lambda c: c.db_version)
    excluded.sort()

    return DeletePlan(
        candidates=tuple(candidates),
        excluded_versions_in_manifest=tuple(excluded),
        bucket=bucket,
        manifest_table=manifest_table,
    )


def execute_delete_plan(
    client,
    plan: DeletePlan,
    *,
    expected_count: int,
    expected_bytes: int,
    bucket: str = DEFAULT_BUCKET,
    manifest_table: str = DEFAULT_MANIFEST_TABLE,
    audit_log: Optional[AuditLog] = None,
    lock_path: Optional[Path] = None,
) -> DeleteResult:
    """Execute the plan after validating expected counts.

    Validation chain (all must pass before any delete):
      1. ``expected_count`` MUST equal ``plan.total_objects`` exactly.
      2. ``expected_bytes`` MUST equal ``plan.total_bytes`` exactly.
      3. Re-fetch the manifest; raise if any candidate's db_version
         now appears in it (race condition with a concurrent release).
      4. Acquire the pipeline release lock (HR-12).

    Per-object delete failures are recorded and the cleanup CONTINUES
    across remaining objects. The result reports both successes and
    failures.

    Raises:
        ExpectedCountMismatch: if expected counts don't match the plan.
        ManifestRaceConditionError: if a candidate is now in the manifest.
        LockContentionError / StaleLockError / CorruptLockError: from
            the release lock.
    """
    # Guard 1 + 2: expected counts
    if expected_count != plan.total_objects:
        raise ExpectedCountMismatch(
            f"--expected-count={expected_count} does not match plan total "
            f"objects {plan.total_objects}. Refusing to execute. Re-run "
            "dry-run to refresh the plan."
        )
    if expected_bytes != plan.total_bytes:
        raise ExpectedCountMismatch(
            f"--expected-bytes={expected_bytes} does not match plan total "
            f"bytes {plan.total_bytes}. Refusing to execute. Re-run "
            "dry-run to refresh the plan."
        )

    log = audit_log if audit_log is not None else make_audit_log()
    log.event(
        "delete_stale_version_dirs_started",
        bucket=bucket,
        manifest_table=manifest_table,
        candidate_versions=[c.db_version for c in plan.candidates],
        total_objects=plan.total_objects,
        total_bytes=plan.total_bytes,
    )

    # Guard 3: re-fetch manifest, defensive against race
    current_manifest = _fetch_manifest_versions(client, manifest_table)
    racing = sorted(
        c.db_version for c in plan.candidates if c.db_version in current_manifest
    )
    if racing:
        log.event(
            "delete_aborted_manifest_race",
            racing_versions=racing,
        )
        raise ManifestRaceConditionError(
            f"Race condition: {len(racing)} candidate version(s) appeared "
            f"in {manifest_table} between plan and execute: {racing}. "
            "A concurrent release happened. Re-run dry-run."
        )

    # Guard 4: acquire pipeline release lock
    deleted_versions: List[str] = []
    deleted_objects = 0
    deleted_bytes = 0
    failed_objects: List[Tuple[str, str]] = []

    try:
        lock_ctx = acquire_release_lock(
            lock_path, initial_step="delete_stale_version_dirs"
        )
        lock = lock_ctx.__enter__()
    except (LockContentionError, StaleLockError, CorruptLockError):
        log.event("delete_aborted_lock_unavailable")
        raise

    try:
        log.event("lock_acquired", pid=lock.pid)

        for c in plan.candidates:
            v_deleted = 0
            v_failed = 0
            v_deleted_bytes = 0
            for path, size in c.objects:
                ok, err = _remove_object(client, bucket, path)
                if ok:
                    v_deleted += 1
                    v_deleted_bytes += size
                else:
                    v_failed += 1
                    failed_objects.append((path, err or "unknown"))

            log.event(
                "version_dir_deleted",
                db_version=c.db_version,
                object_count=c.object_count,
                deleted=v_deleted,
                failed=v_failed,
                deleted_bytes=v_deleted_bytes,
                planned_bytes=c.total_bytes,
            )

            if v_failed == 0:
                deleted_versions.append(c.db_version)
            deleted_objects += v_deleted
            deleted_bytes += v_deleted_bytes

    finally:
        try:
            lock_ctx.__exit__(None, None, None)
        finally:
            log.event("lock_released")

    log.event(
        "delete_complete",
        deleted_versions=deleted_versions,
        deleted_objects_count=deleted_objects,
        deleted_bytes=deleted_bytes,
        failed_objects_count=len(failed_objects),
    )

    return DeleteResult(
        plan=plan,
        deleted_versions=tuple(deleted_versions),
        deleted_objects_count=deleted_objects,
        deleted_bytes=deleted_bytes,
        failed_objects=tuple(failed_objects),
        audit_log_path=log.path,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _fetch_manifest_versions(client, table_name: str) -> set:
    """Fetch every db_version currently in the manifest table."""
    response = client.table(table_name).select("db_version").execute()
    rows = getattr(response, "data", None) or []
    return {
        row.get("db_version") for row in rows
        if isinstance(row, dict) and isinstance(row.get("db_version"), str)
    }


def _list_storage_v_dirs(client, bucket: str) -> List[str]:
    """List top-level v{version}/ directory names in the bucket."""
    items = _list_paginated(client, bucket, "")
    out = []
    for item in items:
        name = (item or {}).get("name") if isinstance(item, dict) else None
        if not isinstance(name, str):
            continue
        if _VERSION_DIR_RE.match(name):
            out.append(name)
    return sorted(out)


def _enumerate_dir_objects(
    client, bucket: str, dir_name: str,
) -> List[Tuple[str, int]]:
    """Recursively walk a directory; return list of (full_path, size_bytes).

    Files with no size metadata are included with size 0 — they still
    need to be deleted. Total-bytes accuracy is best-effort.
    """
    out: List[Tuple[str, int]] = []

    def walk(prefix: str) -> None:
        items = _list_paginated(client, bucket, prefix)
        for item in items:
            name = (item or {}).get("name") if isinstance(item, dict) else None
            if not isinstance(name, str):
                continue
            size = _item_size(item)
            full = f"{prefix}/{name}" if prefix else name
            if size is not None:
                out.append((full, size))
            else:
                walk(full)

    walk(dir_name)
    return out


def _list_paginated(client, bucket: str, prefix: str) -> List[dict]:
    """List all items under a prefix, paginating past the 1000-item limit."""
    items: List[dict] = []
    offset = 0
    page_size = 1000
    while True:
        try:
            page = client.storage.from_(bucket).list(
                path=prefix,
                options={"limit": page_size, "offset": offset},
            )
        except Exception:  # noqa: BLE001
            break
        if not page:
            break
        items.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return items


def _item_size(item: dict) -> Optional[int]:
    metadata = item.get("metadata") if isinstance(item, dict) else None
    if isinstance(metadata, dict):
        size = metadata.get("size")
        if isinstance(size, int):
            return size
    fallback = item.get("size") if isinstance(item, dict) else None
    if isinstance(fallback, int):
        return fallback
    return None


def _remove_object(
    client, bucket: str, path: str,
) -> Tuple[bool, Optional[str]]:
    try:
        client.storage.from_(bucket).remove([path])
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------


def format_plan_text(plan: DeletePlan) -> str:
    lines = [
        "=" * 70,
        f"Stale version-directory cleanup plan",
        f"Bucket:         {plan.bucket}",
        f"Manifest table: {plan.manifest_table}",
        "=" * 70,
        "",
        f"Candidate versions to DELETE (NOT in manifest): "
        f"{plan.total_versions}",
        f"Total objects:  {plan.total_objects:,}",
        f"Total bytes:    {plan.total_bytes:,} ({_fmt_bytes(plan.total_bytes)})",
        "",
        "Per directory:",
    ]
    for c in plan.candidates:
        lines.append(
            f"  {c.dir_path:<35}  {c.object_count:>5,} obj  "
            f"{c.total_bytes:>12,} B  ({_fmt_bytes(c.total_bytes):>10})"
        )

    if plan.excluded_versions_in_manifest:
        lines.extend([
            "",
            f"Excluded (present in {plan.manifest_table}, will NOT be deleted):",
        ])
        for v in plan.excluded_versions_in_manifest:
            lines.append(f"  {v}")

    lines.extend([
        "",
        "─" * 70,
        "DRY-RUN MODE. No deletions performed. To execute, run with:",
        f"  --execute --expected-count {plan.total_objects} "
        f"--expected-bytes {plan.total_bytes}",
        "─" * 70,
    ])
    return "\n".join(lines)


def _fmt_bytes(n: int) -> str:
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
        description=(
            "Delete stale pharmaguide/v.../ directories whose db_version "
            "is NOT in the export_manifest table. Defaults to DRY-RUN."
        ),
    )
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--manifest-table", default=DEFAULT_MANIFEST_TABLE)
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete. Default is dry-run.")
    parser.add_argument("--expected-count", type=int,
                        help="Required with --execute; must equal plan total.")
    parser.add_argument("--expected-bytes", type=int,
                        help="Required with --execute; must equal plan total.")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from supabase_client import get_supabase_client  # noqa: E402

    try:
        client = get_supabase_client()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect to Supabase: {exc}", file=sys.stderr)
        return 1

    plan = compute_delete_plan(
        client, bucket=args.bucket, manifest_table=args.manifest_table,
    )
    print(format_plan_text(plan))

    if not args.execute:
        return 0

    if args.expected_count is None or args.expected_bytes is None:
        print(
            "\nERROR: --execute requires both --expected-count "
            "and --expected-bytes (must match plan totals exactly).",
            file=sys.stderr,
        )
        return 2

    try:
        result = execute_delete_plan(
            client,
            plan,
            expected_count=args.expected_count,
            expected_bytes=args.expected_bytes,
            bucket=args.bucket,
            manifest_table=args.manifest_table,
        )
    except ExpectedCountMismatch as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2
    except ManifestRaceConditionError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 3
    except (LockContentionError, StaleLockError, CorruptLockError) as exc:
        print(f"\nERROR: lock unavailable: {exc}", file=sys.stderr)
        return 4

    print()
    print("─" * 70)
    print(
        f"DELETED: {result.deleted_objects_count:,} objects across "
        f"{len(result.deleted_versions)} versions "
        f"({_fmt_bytes(result.deleted_bytes)})"
    )
    if result.failed_objects:
        print(
            f"FAILED:  {len(result.failed_objects):,} object(s) — see audit log: "
            f"{result.audit_log_path}"
        )
        for path, err in result.failed_objects[:10]:
            print(f"  - {path}: {err}")
        if len(result.failed_objects) > 10:
            print(f"  ... ({len(result.failed_objects) - 10} more)")
    else:
        print(f"All planned deletions succeeded. Audit: {result.audit_log_path}")
    return 0 if result.passed else 5


if __name__ == "__main__":
    import sys
    sys.exit(_main())
