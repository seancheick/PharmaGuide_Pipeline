"""Operational tool for retiring an ACTIVE catalog_releases row.

Implements ADR-0001 P3.4. Wraps registry.retire_release() with
operational safety: dry-run preview, last-ACTIVE-row guard,
last-bundled-row warning, structured audit logging, and a single
explicit override flag for the genuinely-end-of-life case.

Use case
========
When a new OTA release activates, the previous ota_stable row becomes
stale. Its blobs should join the orphan-cleanup pool. Today this would
require raw SQL; this CLI makes it a single call with full state-machine
+ audit safety.

Safety architecture
===================

  Layer 1 — state machine (registry.retire_release):
      Refuses anything that isn't a clean ACTIVE -> RETIRED transition.
      Empty reason rejected before the DB call.

  Layer 2 — operational guards (this module):
      a. Refuse to retire the LAST ACTIVE row in the registry.
         Override: --allow-empty-active.
         Reasoning: emptying the registry makes the protected set go
         empty, which makes the next orphan cleanup eligible to delete
         every blob in shared/details/. That's the 2026-05-12 incident
         class. The override exists for genuine end-of-life only and
         is recorded in the audit event as dangerous_override_used=true.
      b. Soft-warn (no block) when retiring the last ACTIVE bundled row.
         A bundled row anchors the Flutter-side trust model in P1.4. The
         warning surfaces both on stderr AND in the audit event as
         warning_last_bundled_active=true. Not a hard block — bundled
         rows do legitimately need to be retired when superseded.

  Layer 3 — audit log (P1.5a):
      Every retire (dry-run AND execute) emits one JSONL event with:
          event_type, db_version, release_channel, from_state, to_state,
          reason, dry_run, dangerous_override_used,
          warning_last_bundled_active, operator, git_sha, timestamp.

Dry-run vs execute invariant
============================
The plan and warnings produced by --dry-run are byte-for-byte identical
to those produced by --execute (modulo the dry_run field in the audit
event). Dry-run is a true preview — same code path, same checks, no DB
write. Execute refuses if blocked_by is non-empty UNLESS the matching
override flag is present.

Public API
==========
    RetirePlan
    RetireResult
    RetireBlocked         (raised by execute if blocked_by populated, no override)

    compute_retire_plan(client, *, db_version, reason) -> RetirePlan
    execute_retire_plan(client, plan, *, dry_run, allow_empty_active=False,
                        audit_dir=None, now=None, operator=None, git_sha=None)
                        -> RetireResult

CLI
===
    python -m release_safety.retire_release \\
        --db-version 2026.05.11.164208 \\
        --reason "superseded by 2026.05.13.140000" \\
        [--allow-empty-active] \\
        [--audit-dir /path] \\
        [--execute]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .audit_log import AuditLog, DEFAULT_AUDIT_DIR, make_audit_log
from .registry import (
    DEFAULT_TABLE as REGISTRY_TABLE,
    CatalogRelease,
    IllegalStateTransitionError,
    InvalidReleaseFieldError,
    ReleaseChannel,
    ReleaseNotFoundError,
    ReleaseState,
    get_release,
    list_active_releases,
    retire_release as _registry_retire,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RetireBlocked(Exception):
    """Raised by execute_retire_plan when a plan has blocked_by reasons
    that are not cleared by the supplied overrides."""


# ---------------------------------------------------------------------------
# Plan / Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetirePlan:
    """Output of compute_retire_plan. Pure read; no mutation.

    Attributes:
        target: the row that would be retired (always ACTIVE — pre-flight
            checks reject other states before producing a plan).
        reason: operator-supplied reason (already validated non-empty).
        active_count_before: number of ACTIVE rows in registry right now.
        active_count_after: what active_count_before would become after this retire.
        blocked_by: tuple of reasons execution must refuse. Empty when safe.
            Each reason corresponds to an override flag that can clear it.
        warnings: tuple of soft warnings (printed but do NOT block execute).
    """
    target: CatalogRelease
    reason: str
    active_count_before: int
    active_count_after: int
    blocked_by: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RetireResult:
    """Output of execute_retire_plan."""
    retired: Optional[CatalogRelease]   # None on dry-run
    audit_log_path: Path
    dry_run: bool


# ---------------------------------------------------------------------------
# Plan computation
# ---------------------------------------------------------------------------


def compute_retire_plan(
    client,
    *,
    db_version: str,
    reason: str,
    registry_table: str = REGISTRY_TABLE,
) -> RetirePlan:
    """Build a RetirePlan for the operator to review. Read-only.

    Pre-flight checks (raise BEFORE returning a plan):
      - db_version must be non-empty (InvalidReleaseFieldError)
      - reason must be non-empty after stripping (InvalidReleaseFieldError)
      - target row must exist (ReleaseNotFoundError)
      - target row must be ACTIVE (IllegalStateTransitionError)

    Operational guards (recorded in plan.blocked_by; NOT raised):
      - "last_active_row" — would leave 0 ACTIVE rows in registry.
        Cleared by execute_retire_plan(allow_empty_active=True).

    Soft warnings (recorded in plan.warnings; NOT blocking):
      - "last_bundled_active" — retiring the last ACTIVE bundled row.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise InvalidReleaseFieldError(
            "reason must be non-empty (mirrors DB CHECK retired_fields_consistent)"
        )
    target = get_release(client, db_version, table=registry_table)
    if target is None:
        raise ReleaseNotFoundError(f"db_version={db_version!r} does not exist")
    if target.state != ReleaseState.ACTIVE:
        raise IllegalStateTransitionError(
            f"db_version={db_version!r} is in state {target.state.value}; "
            f"only ACTIVE rows can be retired"
        )

    actives_before = list_active_releases(client, table=registry_table)
    active_count_before = len(actives_before)
    active_count_after = active_count_before - 1

    blocked_by: list[str] = []
    warnings: list[str] = []

    if active_count_after == 0:
        blocked_by.append("last_active_row")

    bundled_actives = [r for r in actives_before
                       if r.release_channel == ReleaseChannel.BUNDLED]
    if (
        target.release_channel == ReleaseChannel.BUNDLED
        and len(bundled_actives) == 1
    ):
        warnings.append("last_bundled_active")

    return RetirePlan(
        target=target,
        reason=reason.strip(),
        active_count_before=active_count_before,
        active_count_after=active_count_after,
        blocked_by=tuple(blocked_by),
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Plan execution
# ---------------------------------------------------------------------------


_BLOCKED_BY_OVERRIDES = {
    "last_active_row": "allow_empty_active",
}


def execute_retire_plan(
    client,
    plan: RetirePlan,
    *,
    dry_run: bool = True,
    allow_empty_active: bool = False,
    audit_dir: Optional[Path] = None,
    audit_log: Optional[AuditLog] = None,
    now: Optional[datetime] = None,
    operator: Optional[str] = None,
    git_sha: Optional[str] = None,
    registry_table: str = REGISTRY_TABLE,
) -> RetireResult:
    """Execute the plan or preview it.

    Refuses if plan.blocked_by has any entries that aren't cleared by
    the corresponding override flag. Currently:
      - last_active_row -> cleared by allow_empty_active=True

    On dry_run=True: writes ZERO DB rows but DOES write one audit event
    (with dry_run=true field). Same code path, same warnings — true preview.

    Args:
        client: Supabase client.
        plan: result of compute_retire_plan.
        dry_run: if True, no DB write happens. Audit event still emitted.
        allow_empty_active: override for the last_active_row block.
            Recorded as dangerous_override_used=true in the audit event
            when used.
        audit_dir: directory for audit log. Default DEFAULT_AUDIT_DIR.
        audit_log: pre-constructed AuditLog (test injection). If provided,
            audit_dir is ignored.
        now: deterministic clock for the registry update timestamp.
        operator: defaults to $USER env var.
        git_sha: defaults to git rev-parse HEAD in CWD; null if unresolvable.
        registry_table: catalog_releases table name override.

    Returns:
        RetireResult with retired=None on dry-run.

    Raises:
        RetireBlocked: blocked_by has entries not cleared by overrides.
    """
    overrides_provided = {
        "allow_empty_active": allow_empty_active,
    }
    unmet_blocks = [
        b for b in plan.blocked_by
        if not overrides_provided.get(_BLOCKED_BY_OVERRIDES.get(b, ""), False)
    ]
    # Per ADR-0001 P3.4 sign-off: "execute must refuse if blocked_by is
    # non-empty unless the relevant override is present." Dry-run is
    # explicitly NOT execute — it must produce the same plan + warnings
    # as execute, but never raise. The audit event still fires (so an
    # operator can see what was blocked, in dry-run as well as live).
    if unmet_blocks and not dry_run:
        raise RetireBlocked(
            f"refusing to retire {plan.target.db_version!r}: "
            f"blocked_by={list(unmet_blocks)}. "
            f"Required override flags: "
            f"{[_BLOCKED_BY_OVERRIDES[b] for b in unmet_blocks if b in _BLOCKED_BY_OVERRIDES]}"
        )

    dangerous_override_used = bool(allow_empty_active and "last_active_row" in plan.blocked_by)

    if audit_log is None:
        audit_log = make_audit_log(
            audit_dir=audit_dir,
            release_id=f"retire_{plan.target.db_version}",
            timestamp=now,
        )

    operator_resolved = operator if operator is not None else os.environ.get("USER", "unknown")
    git_sha_resolved = git_sha if git_sha is not None else _resolve_git_sha()

    audit_fields = {
        "db_version": plan.target.db_version,
        "release_channel": plan.target.release_channel.value,
        "from_state": plan.target.state.value,
        "to_state": ReleaseState.RETIRED.value,
        "reason": plan.reason,
        "dry_run": dry_run,
        "dangerous_override_used": dangerous_override_used,
        "warning_last_bundled_active": "last_bundled_active" in plan.warnings,
        "operator": operator_resolved,
        "git_sha": git_sha_resolved,
        "active_count_before": plan.active_count_before,
        "active_count_after": plan.active_count_after,
    }

    if dry_run:
        audit_log.event("catalog_release_retire", **audit_fields)
        return RetireResult(retired=None, audit_log_path=audit_log.path, dry_run=True)

    # Live execute. State-machine + DB CHECKs are still the second line of
    # defense — registry.retire_release will raise if anything is off.
    retired = _registry_retire(
        client,
        plan.target.db_version,
        reason=plan.reason,
        now=now,
        table=registry_table,
    )
    audit_log.event("catalog_release_retire", **audit_fields)
    return RetireResult(retired=retired, audit_log_path=audit_log.path, dry_run=False)


# ---------------------------------------------------------------------------
# Plan formatting (human-readable)
# ---------------------------------------------------------------------------


def format_plan_text(plan: RetirePlan) -> str:
    """Render the plan as human-readable text. Same on dry-run + execute."""
    lines: list[str] = []
    add = lines.append
    add("Retire Release Plan")
    add("=" * 60)
    add(f"  Target db_version : {plan.target.db_version}")
    add(f"  Channel           : {plan.target.release_channel.value}")
    add(f"  Current state     : {plan.target.state.value}")
    add(f"  Reason            : {plan.reason}")
    add(f"  ACTIVE count      : {plan.active_count_before} -> {plan.active_count_after}")
    add("")
    if plan.blocked_by:
        add(f"BLOCKED: {len(plan.blocked_by)} reason(s)")
        for b in plan.blocked_by:
            override = _BLOCKED_BY_OVERRIDES.get(b)
            add(f"  - {b}"
                + (f"   (override: --{override.replace('_', '-')})" if override else ""))
        add("")
    if plan.warnings:
        add(f"WARNINGS: {len(plan.warnings)} (soft, non-blocking)")
        for w in plan.warnings:
            add(f"  - {w}")
        add("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_git_sha() -> Optional[str]:
    """Best-effort git rev-parse HEAD. Returns None on any failure.

    Per ADR-0001 P3.4 sign-off: a missing git context must NOT block a
    legitimate retirement. We log null and continue.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        sha = result.stdout.strip()
        return sha or None
    except (OSError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m release_safety.retire_release",
        description=(
            "Retire an ACTIVE catalog_releases row. Default is dry-run; "
            "pass --execute to write."
        ),
    )
    p.add_argument("--db-version", required=True,
                   help="The db_version of the row to retire.")
    p.add_argument("--reason", required=True,
                   help="Operator-supplied reason. Required, non-empty.")
    p.add_argument(
        "--allow-empty-active",
        action="store_true",
        help=(
            "Override the 'last ACTIVE row' block. Use only for genuine "
            "end-of-life. Recorded as dangerous_override_used=true in audit."
        ),
    )
    p.add_argument(
        "--audit-dir", default=None,
        help=f"Audit log directory. Default: {DEFAULT_AUDIT_DIR}",
    )
    p.add_argument(
        "--execute", action="store_true",
        help="Required to actually retire. Default is dry-run.",
    )
    return p


def _make_supabase_client():
    try:
        from supabase import create_client  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "supabase python client not installed; pip install supabase"
        ) from exc
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) "
            "must be set in the environment"
        )
    return create_client(url, key)


def main(argv: Optional[list[str]] = None) -> int:  # pragma: no cover
    args = _build_arg_parser().parse_args(argv)
    client = _make_supabase_client()
    audit_dir = Path(args.audit_dir) if args.audit_dir else None

    plan = compute_retire_plan(
        client, db_version=args.db_version, reason=args.reason,
    )
    print(format_plan_text(plan))

    # Soft warnings always go to stderr regardless of dry-run.
    if "last_bundled_active" in plan.warnings:
        print(
            "WARNING: This is the last ACTIVE bundled row. The protected-set "
            "computation will lose its Flutter-side anchor until a new bundled "
            "release is registered.",
            file=sys.stderr,
        )

    try:
        result = execute_retire_plan(
            client,
            plan,
            dry_run=not args.execute,
            allow_empty_active=args.allow_empty_active,
            audit_dir=audit_dir,
        )
    except RetireBlocked as exc:
        print(f"\nBLOCKED: {exc}", file=sys.stderr)
        return 2

    if result.dry_run:
        print(f"\n(dry-run: pass --execute to write)\n"
              f"Audit event written to {result.audit_log_path}")
    else:
        print(f"\nRetired {result.retired.db_version} -> RETIRED at "
              f"{result.retired.retired_at.isoformat()}\n"
              f"Audit event written to {result.audit_log_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "RetireBlocked",
    "RetirePlan",
    "RetireResult",
    "compute_retire_plan",
    "execute_retire_plan",
    "format_plan_text",
]
