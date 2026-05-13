"""One-time backfill of the catalog_releases registry from current consumer state.

Implements ADR-0001 P3.3.

What this script does (and what it deliberately doesn't)
========================================================
Bootstraps catalog_releases to the minimum state P3.5 (registry-backed
protected-set) needs to compute correct protection. We insert ONLY rows
that represent a catalog version a consumer could currently be reading:

  - bundled-on-Flutter-main      (channel = bundled)
  - current OTA from manifest    (channel = ota_stable, is_current = true)
  - rollback OTA versions        (channel = ota_stable, is_current = false,
                                   AND v{db_version}/ still exists in storage)

We deliberately do NOT backfill historical rows just because they appear
in old manifests or storage. Those are not consumer-relevant — they would
only inflate the protected set unnecessarily and delay reaping of truly
orphaned blobs.

Dedup
=====
The primary key is db_version. If bundled and current OTA share a
db_version, ONE row is created with channel = ``bundled`` (the more
conservative provenance) and ``notes`` records that it is also the
current OTA. ``flutter_repo_commit`` is set from the Flutter side.

State machine exception
=======================
Rows are inserted directly with state = 'ACTIVE' and activated_at set.
The PENDING -> VALIDATING -> ACTIVE state machine in registry.py is
deliberately bypassed — these versions are already serving live traffic
and have been for some time. The state machine exists to discipline
future ongoing release operations, not to gate retroactive backfill.
This exception is intentional, scoped to backfill, and documented here
so future operators don't introduce a "convenience" PENDING->ACTIVE
shortcut elsewhere.

Idempotency
===========
If a row already exists for a candidate db_version, it is reported as
[skip] and untouched. No row is ever updated by this script — backfill
is insert-only. Re-running the script after a successful backfill yields
zero inserts, zero errors, and N skips (one per row that was inserted
the first time).

Safety
======
- ``--dry-run`` is the DEFAULT.
- ``--execute`` is REQUIRED to insert rows.
- Storage existence is checked from the live bucket via the same client
  used for writes; we do not trust manifest rows alone.
- Detail-index existence (``v{db_version}/detail_index.json``) is
  required for OTA/rollback channels. Missing index -> the row is
  reported under ``rows_skipped_missing_index`` and not inserted.
  Bundled rows tolerate a missing detail_index (the bundled catalog's
  blob references are derived from the Flutter-side LFS catalog DB by
  P1.4/P3.5, not from a Supabase-hosted index).

Public API
==========
    BackfillCandidate                   — dataclass for one prospective row
    BackfillPlan                        — dataclass returned by compute_backfill_plan
    BackfillResult                      — dataclass returned by execute_backfill_plan
    BackfillError                       — base error
    InvalidBackfillEnvironmentError     — flutter repo unreadable, etc.

    compute_backfill_plan(client, *, flutter_repo, ...) -> BackfillPlan
    execute_backfill_plan(client, plan, *, ...) -> BackfillResult
    format_plan_text(plan) -> str

CLI
===
    python -m release_safety.backfill_catalog_releases \\
        --flutter-repo /path/to/PharmaGuide-ai \\
        [--branch main] \\
        [--bucket pharmaguide] \\
        [--manifest-table export_manifest] \\
        [--app-version 1.0.0]   # optional: tagged into bundled_in_app_versions
        [--execute]
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .bundle_alignment import (
    BundleAlignmentError,
    BundleManifestNotFoundError,
    FlutterRepoNotFoundError,
    BranchNotFoundError,
    MalformedBundleManifestError,
    read_flutter_bundle_manifest,
)
from .registry import (
    DEFAULT_TABLE as REGISTRY_TABLE,
    CatalogRelease,
    DuplicateReleaseError,
    InvalidReleaseFieldError,
    ReleaseChannel,
    ReleaseState,
    get_release,
)


DEFAULT_BUCKET = "pharmaguide"
DEFAULT_MANIFEST_TABLE = "export_manifest"
DEFAULT_BRANCH = "main"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BackfillError(Exception):
    """Base class for backfill errors."""


class InvalidBackfillEnvironmentError(BackfillError):
    """Raised when the operator passed environment that cannot be inspected
    safely (e.g. missing Flutter repo when the bundled candidate was requested
    AND not opted out)."""


# ---------------------------------------------------------------------------
# Plan / Candidate dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackfillCandidate:
    """One prospective row for catalog_releases.

    Constructed by ``compute_backfill_plan`` from live state, then either
    skipped (already exists / missing required artifacts) or inserted by
    ``execute_backfill_plan``.
    """
    db_version: str
    release_channel: ReleaseChannel
    flutter_repo_commit: Optional[str]
    detail_index_url: Optional[str]
    bundled_in_app_versions: tuple[str, ...]
    notes: Optional[str]
    # Provenance — populated for the human-readable plan output. Never
    # serialized to the DB.
    sources: tuple[str, ...]


@dataclass(frozen=True)
class BackfillPlan:
    """Output of ``compute_backfill_plan``. Read-only snapshot of what would
    happen on ``--execute``. The plan is safe to log, diff, and audit."""
    candidates: tuple[BackfillCandidate, ...]
    rows_already_exist: tuple[str, ...]              # db_versions in registry already
    rows_skipped_missing_index: tuple[str, ...]      # db_versions with no v{ver}/detail_index.json
    rows_skipped_missing_storage: tuple[str, ...]    # db_versions with no v{ver}/ at all
    bundled_degenerate_reason: Optional[str]         # None when bundled candidate succeeded
    manifest_table: str
    bucket: str


@dataclass(frozen=True)
class BackfillResult:
    """Output of ``execute_backfill_plan``. Mirrors plan structure with
    actual outcomes. ``inserted`` is the list of CatalogRelease rows that
    were successfully written; ``errors`` is per-candidate failure detail."""
    inserted: tuple[CatalogRelease, ...]
    skipped_already_exist: tuple[str, ...]
    errors: tuple[tuple[str, str], ...]              # (db_version, error_message)
    dry_run: bool


# ---------------------------------------------------------------------------
# Plan computation
# ---------------------------------------------------------------------------


def compute_backfill_plan(
    client,
    *,
    flutter_repo: Optional[str] = None,
    branch: str = DEFAULT_BRANCH,
    bucket: str = DEFAULT_BUCKET,
    manifest_table: str = DEFAULT_MANIFEST_TABLE,
    bundled_app_version: Optional[str] = None,
    registry_table: str = REGISTRY_TABLE,
) -> BackfillPlan:
    """Compute what a backfill would insert. Read-only — touches no rows.

    Args:
        client: Supabase client (must support ``.table()`` AND
            ``.storage.from_()``).
        flutter_repo: Path to the Flutter repo for bundled-side detection.
            If None, the bundled candidate is skipped with a degenerate
            reason and only OTA/rollback rows are considered.
        branch: Flutter branch to read for bundled detection (default ``main``).
        bucket: Supabase storage bucket holding v{ver}/ dirs (default ``pharmaguide``).
        manifest_table: Supabase table with the OTA manifest (default
            ``export_manifest``).
        bundled_app_version: If provided, included in
            ``bundled_in_app_versions`` for the bundled row. Optional —
            backfilling without it is fine; future activations will populate.
        registry_table: catalog_releases table name (default ``catalog_releases``).

    Returns:
        BackfillPlan describing every prospective insert + every reason a
        candidate was filtered out.
    """
    # --- 1. Discover bundled candidate (may be degenerate) ----------------
    bundled_db_version: Optional[str] = None
    bundled_flutter_commit: Optional[str] = None
    bundled_degenerate_reason: Optional[str] = None

    if flutter_repo is None:
        bundled_degenerate_reason = "flutter_repo not provided"
    else:
        try:
            snapshot = read_flutter_bundle_manifest(
                flutter_repo_path=flutter_repo,
                branch=branch,
            )
            bundled_db_version = snapshot.db_version
            bundled_flutter_commit = snapshot.commit_sha
        except FlutterRepoNotFoundError as exc:
            bundled_degenerate_reason = f"flutter repo unreadable: {exc}"
        except BranchNotFoundError as exc:
            bundled_degenerate_reason = f"branch {branch!r} not found: {exc}"
        except BundleManifestNotFoundError as exc:
            bundled_degenerate_reason = f"manifest absent on {branch}: {exc}"
        except MalformedBundleManifestError as exc:
            # Corruption — re-raise. We refuse to backfill from a corrupt source.
            raise InvalidBackfillEnvironmentError(
                f"bundled manifest is malformed; refusing to backfill: {exc}"
            ) from exc
        except BundleAlignmentError as exc:
            # Catch-all from the bundle_alignment module
            bundled_degenerate_reason = f"bundle alignment failed: {exc}"

    # --- 2. Discover OTA + rollback candidates from manifest --------------
    manifest_rows = _fetch_manifest_rows(client, manifest_table)
    ota_current_db_versions = [
        r["db_version"] for r in manifest_rows
        if r.get("is_current") is True and isinstance(r.get("db_version"), str)
    ]
    if len(ota_current_db_versions) > 1:
        raise InvalidBackfillEnvironmentError(
            f"manifest table {manifest_table!r} has {len(ota_current_db_versions)} "
            f"is_current=true rows — expected exactly one. Refusing to backfill "
            f"from an inconsistent manifest."
        )
    ota_current = ota_current_db_versions[0] if ota_current_db_versions else None
    rollback_versions = [
        r["db_version"] for r in manifest_rows
        if r.get("is_current") is not True and isinstance(r.get("db_version"), str)
    ]

    # --- 3. Filter: skip rollbacks whose v{ver}/ no longer exists in storage
    rows_skipped_missing_storage: list[str] = []
    surviving_rollbacks: list[str] = []
    for db_version in rollback_versions:
        if _version_dir_exists(client, bucket, db_version):
            surviving_rollbacks.append(db_version)
        else:
            rows_skipped_missing_storage.append(db_version)

    # --- 4. Build candidates with dedup -----------------------------------
    rows_skipped_missing_index: list[str] = []
    candidates_by_version: dict[str, BackfillCandidate] = {}

    # Bundled first (more conservative provenance — wins ties)
    if bundled_db_version is not None:
        bundled_index_path = _detail_index_storage_path(bundled_db_version)
        bundled_index_present = _detail_index_exists(client, bucket, bundled_db_version)
        bundled_notes = None
        bundled_sources = ("flutter-bundled",)
        if bundled_db_version == ota_current:
            bundled_notes = "also current OTA at backfill time"
            bundled_sources = ("flutter-bundled", "ota-current")
        candidates_by_version[bundled_db_version] = BackfillCandidate(
            db_version=bundled_db_version,
            release_channel=ReleaseChannel.BUNDLED,
            flutter_repo_commit=bundled_flutter_commit,
            detail_index_url=bundled_index_path if bundled_index_present else None,
            bundled_in_app_versions=(bundled_app_version,) if bundled_app_version else (),
            notes=bundled_notes,
            sources=bundled_sources,
        )

    # OTA current (only if not already covered by bundled)
    if ota_current and ota_current not in candidates_by_version:
        if not _detail_index_exists(client, bucket, ota_current):
            rows_skipped_missing_index.append(ota_current)
        else:
            candidates_by_version[ota_current] = BackfillCandidate(
                db_version=ota_current,
                release_channel=ReleaseChannel.OTA_STABLE,
                flutter_repo_commit=None,
                detail_index_url=_detail_index_storage_path(ota_current),
                bundled_in_app_versions=(),
                notes="current OTA at backfill time",
                sources=("ota-current",),
            )

    # Rollbacks (only if not already covered by bundled / ota-current)
    for db_version in surviving_rollbacks:
        if db_version in candidates_by_version:
            continue
        if not _detail_index_exists(client, bucket, db_version):
            rows_skipped_missing_index.append(db_version)
            continue
        candidates_by_version[db_version] = BackfillCandidate(
            db_version=db_version,
            release_channel=ReleaseChannel.OTA_STABLE,
            flutter_repo_commit=None,
            detail_index_url=_detail_index_storage_path(db_version),
            bundled_in_app_versions=(),
            notes="rollback OTA at backfill time",
            sources=("ota-rollback",),
        )

    # --- 5. Filter against rows that already exist in registry ------------
    rows_already_exist: list[str] = []
    candidates_to_insert: list[BackfillCandidate] = []
    for db_version, candidate in candidates_by_version.items():
        existing = get_release(client, db_version, table=registry_table)
        if existing is not None:
            rows_already_exist.append(db_version)
            continue
        candidates_to_insert.append(candidate)

    return BackfillPlan(
        candidates=tuple(candidates_to_insert),
        rows_already_exist=tuple(rows_already_exist),
        rows_skipped_missing_index=tuple(rows_skipped_missing_index),
        rows_skipped_missing_storage=tuple(rows_skipped_missing_storage),
        bundled_degenerate_reason=bundled_degenerate_reason,
        manifest_table=manifest_table,
        bucket=bucket,
    )


# ---------------------------------------------------------------------------
# Plan execution
# ---------------------------------------------------------------------------


def execute_backfill_plan(
    client,
    plan: BackfillPlan,
    *,
    dry_run: bool = True,
    now: Optional[datetime] = None,
    registry_table: str = REGISTRY_TABLE,
) -> BackfillResult:
    """Insert the plan's candidates as ACTIVE rows.

    On ``dry_run=True`` (default), no rows are written. The returned
    result has empty ``inserted`` and reflects what the plan said would
    have been skipped as already-existing.

    Continues on per-candidate errors so one bad row doesn't block the
    rest. Errors are returned in ``result.errors``.
    """
    activation_ts = now or datetime.now(timezone.utc)
    activation_iso = _format_timestamp(activation_ts)

    if dry_run:
        return BackfillResult(
            inserted=(),
            skipped_already_exist=plan.rows_already_exist,
            errors=(),
            dry_run=True,
        )

    inserted: list[CatalogRelease] = []
    errors: list[tuple[str, str]] = []
    for candidate in plan.candidates:
        try:
            row = _insert_active_row(
                client,
                candidate=candidate,
                activated_at_iso=activation_iso,
                table=registry_table,
            )
            inserted.append(row)
        except DuplicateReleaseError:
            # TOCTOU — someone inserted between plan and execute. Treat as skip.
            errors.append((candidate.db_version, "already exists (TOCTOU race)"))
        except Exception as exc:  # noqa: BLE001
            # Per-candidate isolation: log and continue.
            errors.append((candidate.db_version, f"{type(exc).__name__}: {exc}"))

    return BackfillResult(
        inserted=tuple(inserted),
        skipped_already_exist=plan.rows_already_exist,
        errors=tuple(errors),
        dry_run=False,
    )


# ---------------------------------------------------------------------------
# Plan formatting (human-readable)
# ---------------------------------------------------------------------------


def format_plan_text(plan: BackfillPlan) -> str:
    """Render plan as a multi-line string suitable for stdout / audit logs."""
    lines: list[str] = []
    add = lines.append
    add("Catalog Releases Backfill Plan")
    add("=" * 60)
    add(f"  Manifest table: {plan.manifest_table}")
    add(f"  Storage bucket: {plan.bucket}")
    add(f"  Bundled side  : "
        f"{'OK' if plan.bundled_degenerate_reason is None else 'DEGENERATE'}")
    if plan.bundled_degenerate_reason is not None:
        add(f"     reason     : {plan.bundled_degenerate_reason}")
    add("")

    add(f"To insert: {len(plan.candidates)} candidate(s)")
    for c in plan.candidates:
        add(f"  + {c.db_version}  channel={c.release_channel.value}  "
            f"sources={','.join(c.sources)}")
        if c.flutter_repo_commit:
            add(f"      flutter_repo_commit = {c.flutter_repo_commit}")
        if c.detail_index_url:
            add(f"      detail_index_url    = {c.detail_index_url}")
        if c.bundled_in_app_versions:
            add(f"      bundled_in_app_versions = "
                f"{list(c.bundled_in_app_versions)}")
        if c.notes:
            add(f"      notes               = {c.notes}")
    add("")

    if plan.rows_already_exist:
        add(f"Skipping (already in registry): {len(plan.rows_already_exist)}")
        for v in plan.rows_already_exist:
            add(f"  [skip] {v}")
        add("")

    if plan.rows_skipped_missing_index:
        add(f"Skipping (missing v{{ver}}/detail_index.json): "
            f"{len(plan.rows_skipped_missing_index)}")
        for v in plan.rows_skipped_missing_index:
            add(f"  [skip] {v}")
        add("")

    if plan.rows_skipped_missing_storage:
        add(f"Skipping (missing v{{ver}}/ in storage): "
            f"{len(plan.rows_skipped_missing_storage)}")
        for v in plan.rows_skipped_missing_storage:
            add(f"  [skip] {v}")
        add("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _detail_index_storage_path(db_version: str) -> str:
    """Storage-relative path to the per-version detail_index.json."""
    return f"v{db_version}/detail_index.json"


def _fetch_manifest_rows(client, manifest_table: str) -> list[dict]:
    """Read all rows from the manifest table (db_version + is_current)."""
    response = (
        client.table(manifest_table)
        .select("db_version, is_current")
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return [r for r in rows if isinstance(r, dict)]


def _version_dir_exists(client, bucket: str, db_version: str) -> bool:
    """Return True if pharmaguide/v{db_version}/ contains at least one object."""
    try:
        items = client.storage.from_(bucket).list(
            path=f"v{db_version}",
            options={"limit": 1, "offset": 0},
        )
    except Exception:
        return False
    return bool(items)


def _detail_index_exists(client, bucket: str, db_version: str) -> bool:
    """Return True if v{db_version}/detail_index.json exists in the bucket."""
    try:
        items = client.storage.from_(bucket).list(
            path=f"v{db_version}",
            options={"limit": 100, "offset": 0},
        )
    except Exception:
        return False
    if not items:
        return False
    for item in items:
        if isinstance(item, dict) and item.get("name") == "detail_index.json":
            return True
    return False


def _insert_active_row(
    client,
    *,
    candidate: BackfillCandidate,
    activated_at_iso: str,
    table: str,
) -> CatalogRelease:
    """Direct INSERT bypassing the state machine — backfill exception only.

    Mirrors the DB CHECK constraints client-side BEFORE the call (so failures
    surface as InvalidReleaseFieldError, not opaque DB errors)."""
    if (
        candidate.release_channel == ReleaseChannel.BUNDLED
        and not candidate.flutter_repo_commit
    ):
        raise InvalidReleaseFieldError(
            "bundled channel requires flutter_repo_commit (mirrors DB CHECK "
            "bundled_requires_flutter_commit)"
        )

    payload: dict[str, Any] = {
        "db_version": candidate.db_version,
        "state": ReleaseState.ACTIVE.value,
        "release_channel": candidate.release_channel.value,
        "activated_at": activated_at_iso,
        "bundled_in_app_versions": list(candidate.bundled_in_app_versions),
    }
    if candidate.flutter_repo_commit is not None:
        payload["flutter_repo_commit"] = candidate.flutter_repo_commit
    if candidate.detail_index_url is not None:
        payload["detail_index_url"] = candidate.detail_index_url
    if candidate.notes is not None:
        payload["notes"] = candidate.notes

    response = client.table(table).insert(payload).execute()
    rows = getattr(response, "data", None) or []
    if not rows:
        raise BackfillError(
            f"insert for db_version={candidate.db_version!r} returned no rows"
        )
    return CatalogRelease.from_row(rows[0])


def _format_timestamp(ts: datetime) -> str:
    """ISO-8601 UTC. Same convention as registry._format_timestamp."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m release_safety.backfill_catalog_releases",
        description=(
            "Backfill catalog_releases registry from current consumer state. "
            "Default is dry-run; pass --execute to write."
        ),
    )
    p.add_argument(
        "--flutter-repo",
        required=False,
        help="Path to PharmaGuide Flutter repo. Omit to skip bundled side.",
    )
    p.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=f"Flutter branch to inspect for bundled (default: {DEFAULT_BRANCH})",
    )
    p.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"Supabase storage bucket (default: {DEFAULT_BUCKET})",
    )
    p.add_argument(
        "--manifest-table",
        default=DEFAULT_MANIFEST_TABLE,
        help=f"Supabase manifest table (default: {DEFAULT_MANIFEST_TABLE})",
    )
    p.add_argument(
        "--app-version",
        required=False,
        help="If provided, included in bundled_in_app_versions for the bundled row.",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Required to actually insert rows. Default is dry-run.",
    )
    return p


def _make_supabase_client():
    """Lazily import supabase so the module can be unit-tested without it."""
    try:
        from supabase import create_client  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise InvalidBackfillEnvironmentError(
            "supabase python client not installed; pip install supabase"
        ) from exc
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise InvalidBackfillEnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) "
            "must be set in the environment"
        )
    return create_client(url, key)


def main(argv: Optional[list[str]] = None) -> int:  # pragma: no cover
    args = _build_arg_parser().parse_args(argv)
    client = _make_supabase_client()
    plan = compute_backfill_plan(
        client,
        flutter_repo=args.flutter_repo,
        branch=args.branch,
        bucket=args.bucket,
        manifest_table=args.manifest_table,
        bundled_app_version=args.app_version,
    )
    print(format_plan_text(plan))

    if not args.execute:
        print("\n(dry-run: pass --execute to write)")
        return 0

    print("\nExecuting…")
    result = execute_backfill_plan(client, plan, dry_run=False)
    print(f"  inserted: {len(result.inserted)}")
    print(f"  skipped (already exist): {len(result.skipped_already_exist)}")
    if result.errors:
        print(f"  errors: {len(result.errors)}")
        for db_version, msg in result.errors:
            print(f"    [error] {db_version}: {msg}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "DEFAULT_BUCKET",
    "DEFAULT_MANIFEST_TABLE",
    "DEFAULT_BRANCH",
    "BackfillError",
    "InvalidBackfillEnvironmentError",
    "BackfillCandidate",
    "BackfillPlan",
    "BackfillResult",
    "compute_backfill_plan",
    "execute_backfill_plan",
    "format_plan_text",
]
