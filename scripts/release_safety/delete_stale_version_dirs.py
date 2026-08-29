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

    # Guard 4: acquire pipeline release lock. Guard 3 (the manifest race
    # recheck) runs INSIDE it — a recheck done before the lock leaves a
    # window in which a concurrent release can re-register a candidate
    # between the check and the grab.
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

        # Guard 3 (FINAL, under the lock): no candidate may have re-entered
        # the manifest. Nothing has been deleted yet, so this aborts clean.
        current_manifest = _fetch_manifest_versions(client, manifest_table)
        racing = sorted(
            c.db_version for c in plan.candidates
            if c.db_version in current_manifest
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

        for c in plan.candidates:
            v_deleted = 0
            v_failed = 0
            v_deleted_bytes = 0
            v_failed_paths = set()
            for path, size in c.objects:
                ok, err = _remove_object(client, bucket, path)
                if ok:
                    v_deleted += 1
                    v_deleted_bytes += size
                else:
                    v_failed += 1
                    v_failed_paths.add(path)
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

            # Absence proof: remove()'s response is a claim, the listing is
            # the authority. Residue keeps the version out of
            # deleted_versions so the operator sees unfinished work.
            try:
                residue = _enumerate_dir_objects(client, bucket, c.dir_path)
            except Exception as exc:  # noqa: BLE001 — unknown ≠ deleted.
                v_failed += 1
                failed_objects.append((
                    c.dir_path,
                    f"absence proof failed: {type(exc).__name__}: {exc}",
                ))
                residue = None
            if residue:
                for path, _size in residue:
                    if path in v_failed_paths:
                        continue  # already reported by its delete failure
                    v_failed += 1
                    failed_objects.append((
                        path, "residual: still listed after deletion",
                    ))
            if v_failed == 0 and residue is not None:
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
# Approval artifact — execution binds to the reviewed set, not a recount
# ---------------------------------------------------------------------------


class ApprovalArtifactError(ValueError):
    """The stale-dir approval artifact cannot authorize an execution."""


def _plan_fingerprint(candidates) -> str:
    """Digest over sorted (db_version, path, size) records. Totals-only
    approval let a DIFFERENT directory with identical count/bytes pass; this
    binds the exact reviewed set."""
    import hashlib

    lines = "\n".join(
        f"{c['db_version']}\t{r['path']}\t{r['size']}"
        for c in sorted(candidates, key=lambda c: c["db_version"])
        for r in sorted(c["objects"], key=lambda r: r["path"])
    )
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def plan_to_artifact(plan: "DeletePlan", *, manifest_versions) -> dict:
    """Convert a freshly computed dry plan into the executable approval JSON."""
    import hashlib

    candidates = [
        {
            "db_version": c.db_version,
            "dir_path": c.dir_path,
            "object_count": c.object_count,
            "bytes": c.total_bytes,
            "objects": [
                {"path": path, "size": size}
                for path, size in sorted(c.objects)
            ],
        }
        for c in plan.candidates
    ]
    return {
        "artifact_kind": "stale_version_dirs_approval",
        "total_count": plan.total_objects,
        "total_bytes": plan.total_bytes,
        "candidates": candidates,
        "retained_manifest_digest": hashlib.sha256(
            "\n".join(sorted(manifest_versions)).encode("utf-8")
        ).hexdigest(),
        "fingerprint": _plan_fingerprint(candidates),
    }


def _load_artifact(path) -> dict:
    import json as _json

    if path is None:
        raise ApprovalArtifactError(
            "--approval-report is required: execution acts on the REVIEWED "
            "artifact, never on a fresh recount."
        )
    try:
        data = _json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ApprovalArtifactError(f"cannot read approval report: {exc}")
    if data.get("artifact_kind") != "stale_version_dirs_approval":
        raise ApprovalArtifactError("not a stale-dir approval artifact")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ApprovalArtifactError("artifact approves no candidates")
    for c in candidates:
        if (
            not isinstance(c, dict)
            or not isinstance(c.get("db_version"), str)
            or not isinstance(c.get("objects"), list)
            or not c["objects"]
            or not all(
                isinstance(r, dict)
                and isinstance(r.get("path"), str)
                and r["path"].startswith(f"v{c['db_version']}/")
                and isinstance(r.get("size"), int)
                for r in c["objects"]
            )
        ):
            raise ApprovalArtifactError(
                f"malformed candidate record: {c.get('db_version')!r}"
            )
    if _plan_fingerprint(candidates) != data.get("fingerprint"):
        raise ApprovalArtifactError(
            "artifact records do not reproduce its own fingerprint "
            "(edited or corrupted)"
        )
    record_count = sum(len(c["objects"]) for c in candidates)
    record_bytes = sum(r["size"] for c in candidates for r in c["objects"])
    if record_count != data.get("total_count") or record_bytes != data.get("total_bytes"):
        raise ApprovalArtifactError("artifact totals do not match its records")
    return data


def execute_from_artifact(
    client,
    *,
    approval_report,
    expected_count,
    expected_bytes,
    fingerprint,
    bucket: str = DEFAULT_BUCKET,
    manifest_table: str = DEFAULT_MANIFEST_TABLE,
    audit_log: Optional[AuditLog] = None,
    lock_path: Optional[Path] = None,
) -> int:
    """Delete exactly the reviewed set. Returns a process exit code.

    Under the release lock: recompute the fresh plan and require it to
    reproduce the approved fingerprint EXACTLY (a swapped candidate with
    identical totals, or a same-path size drift, refuses everything), then
    delegate to execute_delete_plan — which rechecks the manifest inside the
    lock and proves each directory absent afterwards.
    """
    try:
        artifact = _load_artifact(approval_report)
    except ApprovalArtifactError as exc:
        print(f"[refused] {exc}")
        return 2
    for label, flag, key in (
        ("--expected-count", expected_count, "total_count"),
        ("--expected-bytes", expected_bytes, "total_bytes"),
        ("--fingerprint", fingerprint, "fingerprint"),
    ):
        if flag is None or flag != artifact[key]:
            print(
                f"[refused] {label} {flag!r} does not match the artifact's "
                f"{artifact[key]!r}."
            )
            return 2

    # The fresh-set proof AND the deletion share one lock hold (re-entrant
    # for the nested acquire inside execute_delete_plan) — no window between
    # proving the set and acting on it.
    try:
        outer_lock = acquire_release_lock(
            lock_path, initial_step="delete_stale_version_dirs artifact",
        )
        outer_lock.__enter__()
    except (LockContentionError, StaleLockError, CorruptLockError) as exc:
        print(f"[refused] release lock unavailable: {exc}")
        return 1
    try:
        fresh_plan = compute_delete_plan(
            client, bucket=bucket, manifest_table=manifest_table,
        )
        fresh_artifact = plan_to_artifact(fresh_plan, manifest_versions=set())
        if fresh_artifact["fingerprint"] != artifact["fingerprint"]:
            print(
                "[refused] the stale-directory set has CHANGED since approval "
                f"(fresh {fresh_artifact['total_count']} objects / "
                f"{fresh_artifact['fingerprint'][:16]}… vs approved "
                f"{artifact['total_count']} / {artifact['fingerprint'][:16]}…). "
                "Re-run the dry plan and review again. Nothing deleted."
            )
            return 2

        result = execute_delete_plan(
            client, fresh_plan,
            expected_count=artifact["total_count"],
            expected_bytes=artifact["total_bytes"],
            bucket=bucket,
            manifest_table=manifest_table,
            audit_log=audit_log,
            lock_path=lock_path,
        )
    except (ExpectedCountMismatch, ManifestRaceConditionError) as exc:
        print(f"[refused] {exc}")
        return 2
    finally:
        outer_lock.__exit__(None, None, None)

    print(
        f"Deleted {result.deleted_objects_count} object(s) / "
        f"{result.deleted_bytes:,} bytes across "
        f"{len(result.deleted_versions)} director(ies); "
        f"{len(result.failed_objects)} failure(s)."
    )
    return 0 if not result.failed_objects else 1


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
    """List ALL items under a prefix, or raise — never return a truncation.

    The previous ``except: break`` turned a mid-listing failure into an
    apparently valid partial result. Fed into compute_delete_plan, a
    partially-enumerated directory gets partially deleted and then reported
    done — the origin of the 1-object residue dirs. Transient blips are
    retried; a give-up raises so the caller fails closed.
    """
    from .transient import retry_transient

    items: List[dict] = []
    offset = 0
    page_size = 1000
    while True:
        page = retry_transient(
            lambda offset=offset: client.storage.from_(bucket).list(
                path=prefix,
                options={"limit": page_size, "offset": offset},
            ),
            max_attempts=4,
        )
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
# Completeness-bearing version-directory inventory (read-only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionDirEntry:
    """One v{version}/ directory: exact object/byte expectations + status."""

    version: str
    in_manifest: bool
    object_count: int
    total_bytes: int
    complete: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class VersionDirInventory:
    """The reviewable dry report a stale-dir cleanup is approved against."""

    dirs: Tuple[VersionDirEntry, ...]
    failures: Tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.failures and all(d.complete for d in self.dirs)

    @property
    def stale_dirs(self) -> Tuple[VersionDirEntry, ...]:
        return tuple(d for d in self.dirs if not d.in_manifest)

    def text_report(self) -> str:
        lines = [
            "Version-directory inventory "
            + ("(COMPLETE)" if self.complete else "(INCOMPLETE — do not act)"),
            f"  {'version':<24} {'manifest':<9} {'objects':>8} {'bytes':>12}  status",
        ]
        for d in self.dirs:
            lines.append(
                f"  v{d.version:<23} {'YES' if d.in_manifest else 'no':<9} "
                f"{d.object_count:>8} {d.total_bytes:>12,}  "
                f"{'ok' if d.complete else f'UNLISTABLE ({d.error})'}"
            )
        stale = self.stale_dirs
        lines.append(
            f"  stale (not in manifest): {len(stale)} dir(s), "
            f"{sum(d.object_count for d in stale)} object(s), "
            f"{sum(d.total_bytes for d in stale):,} bytes"
        )
        if self.failures:
            lines.append(f"  failures: {'; '.join(self.failures)}")
        return "\n".join(lines)


def inventory_version_dirs(
    client,
    *,
    bucket: str = DEFAULT_BUCKET,
    manifest_table: str = DEFAULT_MANIFEST_TABLE,
) -> VersionDirInventory:
    """Enumerate every v{version}/ directory with exact object/byte counts.

    Read-only. A directory that cannot be fully enumerated is included with
    ``complete=False`` and zeroed counts — never with a truncated count that
    looks exact. The stale-dir cleanup (approval-gated) must require
    ``inventory.complete`` before acting.
    """
    manifest_versions = _fetch_manifest_versions(client, manifest_table)
    dirs = []
    failures = []
    for dir_name in _list_storage_v_dirs(client, bucket):
        version = dir_name[1:]
        try:
            objects = _enumerate_dir_objects(client, bucket, dir_name)
        except Exception as exc:  # noqa: BLE001 — reported, never truncated.
            failures.append(f"{dir_name}: {type(exc).__name__}: {exc}")
            dirs.append(VersionDirEntry(
                version=version,
                in_manifest=version in manifest_versions,
                object_count=0,
                total_bytes=0,
                complete=False,
                error=f"{type(exc).__name__}",
            ))
            continue
        dirs.append(VersionDirEntry(
            version=version,
            in_manifest=version in manifest_versions,
            object_count=len(objects),
            total_bytes=sum(size for _p, size in objects),
            complete=True,
        ))
    return VersionDirInventory(dirs=tuple(dirs), failures=tuple(failures))


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
    parser.add_argument("--approval-out",
                        help="Dry run: write the executable approval JSON here.")
    parser.add_argument("--approval-report",
                        help="Execute: the reviewed approval JSON to act on.")
    parser.add_argument("--fingerprint",
                        help="Execute: must equal the artifact's fingerprint.")
    parser.add_argument("--lock-path", type=Path, default=None)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from supabase_client import get_supabase_client  # noqa: E402

    try:
        client = get_supabase_client()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect to Supabase: {exc}", file=sys.stderr)
        return 1

    if args.execute:
        return execute_from_artifact(
            client,
            approval_report=args.approval_report,
            expected_count=args.expected_count,
            expected_bytes=args.expected_bytes,
            fingerprint=args.fingerprint,
            bucket=args.bucket,
            manifest_table=args.manifest_table,
            lock_path=args.lock_path,
        )

    plan = compute_delete_plan(
        client, bucket=args.bucket, manifest_table=args.manifest_table,
    )
    print(format_plan_text(plan))
    if args.approval_out:
        import json as _json

        manifest_versions = _fetch_manifest_versions(
            client, args.manifest_table,
        )
        artifact = plan_to_artifact(plan, manifest_versions=manifest_versions)
        out = Path(args.approval_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps(artifact, indent=2, sort_keys=True))
        print(f"\nApproval artifact written to {out}")
        print(
            "To execute this exact reviewed set:\n"
            f"  --execute --approval-report {out} "
            f"--expected-count {artifact['total_count']} "
            f"--expected-bytes {artifact['total_bytes']} "
            f"--fingerprint {artifact['fingerprint']}"
        )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
