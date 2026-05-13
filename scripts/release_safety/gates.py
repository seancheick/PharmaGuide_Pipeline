"""Cleanup gates orchestrator (ADR-0001 P1.5b).

This module is the integration layer for P1.1-P1.5a primitives. It is
the SINGLE entry point that the cleanup wrapper (P1.6) calls before
any destructive action.

Gate sequence
=============
The gates run in this order. Lock acquisition + index validation +
protected-set computation are PRECONDITIONS — failure short-circuits
because subsequent gates cannot safely compute. Gate 1, 2, 3 and the
degenerate-in-execute check AGGREGATE — all are evaluated, all
failures are collected, the operator sees every problem in one pass.

    Step 1: Lock acquisition          (HR-12; EXECUTE only; precondition)
    Step 2: dist/detail_index.json    (HR-11; precondition)
    Step 3: Protected-set computation (HR-1, HR-2; precondition for hard
                                       failure; degenerate aggregates)
    Step 4: Degenerate-in-EXECUTE     (per P1.5b sign-off: aggregate)
    Step 5: Gate 1 — Bundle alignment (HR-13; aggregate; overridable)
    Step 6: Gate 2 — Blast-radius     (HR-4; aggregate; overridable with
                                       matching --expected-count)
    Step 7: Gate 3 — Live-version     (aggregate; non-overridable)

Mode semantics (HR-3)
=====================
DRY_RUN:
  - Lock NOT required (read-only operation per HR-12).
  - Degenerate protected set is allowed; logs an informational event.
  - All gates evaluate normally; failures still return passed=False so
    the caller sees the problem before promoting to EXECUTE.
EXECUTE:
  - Lock REQUIRED. Lock acquisition failure is a precondition failure
    (short-circuit), not aggregated.
  - Degenerate protected set is a non-overridable failure (aggregated).
  - Bundle misalignment is overridable only via overrides.bundle_mismatch_reason
    (a written reason captured in the audit log).
  - Blast-radius exceedance requires overrides.expected_count exactly
    matching the actual deletion count.

Idempotency (HR-9)
==================
Two consecutive evaluate_cleanup_gates() calls against unchanged inputs
produce identical GateResult shapes and identical decision-event content
in the audit log (modulo timestamps and the per-call release_id). The
gate sequence is deterministic; failure ordering is deterministic;
ProtectedBlobSet frozensets are stable.

Audit log (HR-6)
================
Every decision is logged to the AuditLog (provided or auto-created):
  gate_evaluation_started, lock_acquired, lock_released,
  index_validated, protected_set_computed,
  degenerate_protection_allowed_dry_run,
  gate_passed, gate_failed, gate_skipped,
  gate_evaluation_complete

Audit log is written even when gates fail — the failure record is the
evidence that the safety primitive worked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, List, Optional, Union

from .audit_log import AuditLog, make_audit_log
from .bundle_alignment import (
    BundleAlignmentError,
    check_bundle_alignment,
)
from .index_validator import (
    IndexValidationError,
    validate_detail_index,
)
from .lock import (
    CorruptLockError,
    LockContentionError,
    StaleLockError,
    acquire_release_lock,
)
from .protected_blobs import (
    BundleCatalogQueryError,
    MalformedBundleCatalogError,
    ProtectedBlobSet,
    ProtectedBlobSetError,
    compute_protected_blob_set,
)


DEFAULT_BLAST_RADIUS_THRESHOLD = 0.05  # 5% of storage
DEFAULT_BUNDLED_MANIFEST_PATH = "assets/db/export_manifest.json"
DEFAULT_DIST_INDEX_FILENAME = "detail_index.json"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class GateMode(Enum):
    """Mode for gate evaluation. Default is DRY_RUN per HR-3 (cleanup
    defaults to dry-run; real execution requires explicit --execute)."""

    DRY_RUN = "dry_run"
    EXECUTE = "execute"


@dataclass(frozen=True)
class GateOverrides:
    """Operator-supplied overrides for individual gates.

    Each gate that supports an override looks for its specific field;
    None means "no override supplied". When an override is used, it is
    captured in the audit log so the decision is traceable later.
    """

    # Override for Gate 1 (bundle alignment). Must be a non-empty
    # written reason; the audit log captures it verbatim. The pipeline
    # CLI surface should require quoting/non-empty validation upstream.
    bundle_mismatch_reason: Optional[str] = None

    # Override for Gate 2 (blast-radius). Must equal the actual
    # would_delete_count exactly; a wrong value is treated the same as
    # no override (still fails).
    expected_count: Optional[int] = None


@dataclass(frozen=True)
class GateFailure:
    """A single gate's failure record. Multiple GateFailures may be
    collected in one GateResult.failures list (aggregation per
    P1.5b sign-off)."""

    gate_name: str
    reason: str
    overridable: bool
    override_used: bool
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    """Result of evaluate_cleanup_gates.

    ``passed`` is True iff every aggregated gate passed AND no precondition
    short-circuited. The cleanup wrapper (P1.6) treats this as the single
    go/no-go signal.
    """

    passed: bool
    mode: GateMode
    protected_set: Optional[ProtectedBlobSet]      # None when index validation failed
    deletion_candidates: frozenset                  # candidates AFTER protection filter
    would_delete_count: int
    would_delete_pct: float
    failures: List[GateFailure]                     # empty when passed
    audit_log_path: Path

    def failure_summary(self) -> str:
        """Human-readable summary of all aggregated failures.

        Used by P1.6 wire-in to print a single block to stderr when
        cleanup is rejected. Each failure shows its name, the reason,
        and whether it is overridable.
        """
        if self.passed:
            return "All gates passed."
        lines = [f"Cleanup REJECTED — {len(self.failures)} gate failure(s):"]
        for i, f in enumerate(self.failures, 1):
            tag = " (overridable)" if f.overridable else " (NOT overridable)"
            lines.append(f"  {i}. [{f.gate_name}]{tag}")
            for ln in f.reason.splitlines():
                lines.append(f"     {ln}")
        lines.append(f"\nFull audit log: {self.audit_log_path}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_cleanup_gates(
    flutter_repo_path: Union[Path, str],
    dist_dir: Union[Path, str],
    *,
    candidate_blobs: Iterable[str],
    storage_total: int,
    mode: GateMode = GateMode.DRY_RUN,
    branch: str = "main",
    blast_radius_threshold: float = DEFAULT_BLAST_RADIUS_THRESHOLD,
    overrides: GateOverrides = GateOverrides(),
    audit_log: Optional[AuditLog] = None,
    lock_path: Optional[Path] = None,
) -> GateResult:
    """Evaluate the cleanup gate sequence and return a single go/no-go.

    Args:
        flutter_repo_path: Flutter repo root (for HR-13 bundle alignment).
        dist_dir: directory containing freshly-built dist/ artifacts.
        candidate_blobs: blob hashes that the caller is proposing to delete.
            The gate filters this against the protected set; only the
            difference becomes ``deletion_candidates`` in the result.
        storage_total: total blob count in storage (for blast-radius pct).
        mode: DRY_RUN (default; safe; no lock) or EXECUTE.
        branch: Flutter branch to read bundled manifest from. Default "main".
        blast_radius_threshold: fractional limit for Gate 2. Default 5%.
        overrides: operator-supplied override values (see GateOverrides).
        audit_log: explicit AuditLog to write to. If None, a fresh
            ``make_audit_log()`` is created.
        lock_path: explicit lock file path. None = the default in
            scripts/release_safety/lock.py.

    Returns:
        ``GateResult`` with ``passed``, aggregated ``failures``, and
        the path to the audit log written during evaluation.
    """
    flutter_repo_path = Path(flutter_repo_path)
    dist_dir = Path(dist_dir)

    log = audit_log if audit_log is not None else make_audit_log()
    log.event(
        "gate_evaluation_started",
        mode=mode.value,
        flutter_repo_path=str(flutter_repo_path),
        dist_dir=str(dist_dir),
        branch=branch,
        blast_radius_threshold=blast_radius_threshold,
        storage_total=storage_total,
        candidate_count=sum(1 for _ in candidate_blobs)
            if isinstance(candidate_blobs, (list, tuple, set, frozenset))
            else None,
    )

    # Materialize candidate_blobs once (it may be a generator).
    candidate_blobs = frozenset(candidate_blobs)

    # ------------------------------------------------------------------
    # PRECONDITION 1: lock acquisition (EXECUTE only; short-circuits)
    # ------------------------------------------------------------------
    lock_ctx = None
    if mode == GateMode.EXECUTE:
        try:
            lock_ctx = acquire_release_lock(
                lock_path, initial_step="evaluate_cleanup_gates"
            )
            lock = lock_ctx.__enter__()
            log.event(
                "lock_acquired",
                pid=lock.pid,
                lock_path=str(lock.lock_path),
            )
        except (LockContentionError, StaleLockError, CorruptLockError) as e:
            log.event(
                "gate_failed",
                gate_name="lock_acquisition",
                reason=str(e),
                error_type=type(e).__name__,
            )
            log.event("gate_evaluation_complete", passed=False, failure_count=1)
            return GateResult(
                passed=False, mode=mode,
                protected_set=None,
                deletion_candidates=frozenset(),
                would_delete_count=0,
                would_delete_pct=0.0,
                failures=[GateFailure(
                    gate_name="lock_acquisition",
                    reason=str(e),
                    overridable=False,
                    override_used=False,
                    detail={"error_type": type(e).__name__},
                )],
                audit_log_path=log.path,
            )

    try:
        return _run_gates_after_lock(
            log=log,
            mode=mode,
            flutter_repo_path=flutter_repo_path,
            dist_dir=dist_dir,
            candidate_blobs=candidate_blobs,
            storage_total=storage_total,
            branch=branch,
            blast_radius_threshold=blast_radius_threshold,
            overrides=overrides,
        )
    finally:
        if lock_ctx is not None:
            try:
                lock_ctx.__exit__(None, None, None)
            finally:
                log.event("lock_released")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_gates_after_lock(
    *,
    log: AuditLog,
    mode: GateMode,
    flutter_repo_path: Path,
    dist_dir: Path,
    candidate_blobs: frozenset,
    storage_total: int,
    branch: str,
    blast_radius_threshold: float,
    overrides: GateOverrides,
) -> GateResult:
    """Run preconditions + aggregating gates with the lock already held
    (or not, for dry-run mode)."""

    # ------------------------------------------------------------------
    # PRECONDITION 2: dist/detail_index.json validation
    # ------------------------------------------------------------------
    dist_index_path = dist_dir / DEFAULT_DIST_INDEX_FILENAME
    try:
        validate_detail_index(dist_index_path)
        log.event("index_validated", path=str(dist_index_path))
    except IndexValidationError as e:
        return _short_circuit_failure(
            log=log, mode=mode,
            failure=GateFailure(
                gate_name="index_validation",
                reason=str(e),
                overridable=False, override_used=False,
                detail={"error_type": type(e).__name__,
                        "path": str(dist_index_path)},
            ),
        )

    # ------------------------------------------------------------------
    # PRECONDITION 3: protected-set computation
    # Hard failures (corruption) short-circuit. Degenerate aggregates.
    # ------------------------------------------------------------------
    try:
        protected_set = compute_protected_blob_set(
            flutter_repo_path, dist_dir, branch=branch,
        )
        log.event(
            "protected_set_computed",
            bundled_version=protected_set.bundled_version,
            dist_version=protected_set.dist_version,
            bundled_count=protected_set.bundled_count,
            dist_count=protected_set.dist_count,
            union_count=protected_set.union_count,
            intersection_count=protected_set.intersection_count,
            degenerate=protected_set.degenerate,
            degenerate_reason=protected_set.degenerate_reason,
        )
    except (
        MalformedBundleCatalogError,
        BundleCatalogQueryError,
        ProtectedBlobSetError,
        IndexValidationError,                # could re-raise from inner validate
    ) as e:
        return _short_circuit_failure(
            log=log, mode=mode,
            failure=GateFailure(
                gate_name="protected_set_computation",
                reason=str(e),
                overridable=False, override_used=False,
                detail={"error_type": type(e).__name__},
            ),
        )

    # ------------------------------------------------------------------
    # AGGREGATING FAILURES from here on
    # ------------------------------------------------------------------
    failures: List[GateFailure] = []

    # --- Step 4: degenerate-in-EXECUTE (aggregate per P1.5b sign-off) ---
    if protected_set.degenerate:
        if mode == GateMode.EXECUTE:
            failures.append(GateFailure(
                gate_name="degenerate_protection",
                reason=(
                    "Protected set is degenerate (bundled side unavailable). "
                    "Execute mode rejects this — dist-only protection recreates "
                    "the 2026-05-12 failure mode.\n"
                    f"  reason: {protected_set.degenerate_reason}"
                ),
                overridable=False, override_used=False,
                detail={"degenerate_reason": protected_set.degenerate_reason},
            ))
            log.event(
                "gate_failed",
                gate_name="degenerate_protection",
                reason=protected_set.degenerate_reason,
            )
        else:
            log.event(
                "degenerate_protection_allowed_dry_run",
                reason=protected_set.degenerate_reason,
            )

    # --- Step 5: Gate 1 — Bundle alignment (HR-13) ----------------------
    _evaluate_gate_1_bundle_alignment(
        log=log,
        flutter_repo_path=flutter_repo_path,
        protected_set=protected_set,
        branch=branch,
        overrides=overrides,
        failures=failures,
    )

    # --- Step 6: Gate 2 — Blast-radius (HR-4) ---------------------------
    deletion_candidates = candidate_blobs - protected_set.protected
    would_delete_count = len(deletion_candidates)
    would_delete_pct = (
        would_delete_count / storage_total if storage_total > 0 else 0.0
    )
    _evaluate_gate_2_blast_radius(
        log=log,
        would_delete_count=would_delete_count,
        would_delete_pct=would_delete_pct,
        storage_total=storage_total,
        blast_radius_threshold=blast_radius_threshold,
        overrides=overrides,
        failures=failures,
    )

    # --- Step 7: Gate 3 — Live-version sanity ---------------------------
    if len(protected_set.protected) == 0:
        failures.append(GateFailure(
            gate_name="live_version_sanity",
            reason=(
                "Protected set is empty — refusing to permit any deletion. "
                "This usually means both bundled and dist sides have no blob "
                "references, which would be a pipeline data integrity issue."
            ),
            overridable=False, override_used=False,
            detail={"protected_count": 0},
        ))
        log.event("gate_failed", gate_name="live_version_sanity",
                  reason="protected set is empty")
    else:
        log.event("gate_passed", gate_name="live_version_sanity",
                  protected_count=len(protected_set.protected))

    passed = len(failures) == 0
    log.event(
        "gate_evaluation_complete",
        passed=passed,
        failure_count=len(failures),
        failed_gates=[f.gate_name for f in failures],
    )

    return GateResult(
        passed=passed, mode=mode,
        protected_set=protected_set,
        deletion_candidates=deletion_candidates,
        would_delete_count=would_delete_count,
        would_delete_pct=would_delete_pct,
        failures=failures,
        audit_log_path=log.path,
    )


def _evaluate_gate_1_bundle_alignment(
    *,
    log: AuditLog,
    flutter_repo_path: Path,
    protected_set: ProtectedBlobSet,
    branch: str,
    overrides: GateOverrides,
    failures: List[GateFailure],
) -> None:
    """Gate 1: bundled-on-branch db_version must match dist db_version,
    or be overridden with a written reason.

    When the protected set is degenerate (bundled side unavailable),
    bundle alignment cannot be meaningfully checked — log a skip and
    return without aggregating a separate failure (the degenerate
    failure already captured the same root cause)."""
    if protected_set.degenerate:
        log.event(
            "gate_skipped",
            gate_name="bundle_alignment",
            reason="protected set is degenerate; bundle alignment check not meaningful",
        )
        return

    try:
        alignment = check_bundle_alignment(
            flutter_repo_path,
            protected_set.dist_version,
            branch=branch,
            raise_on_misalignment=False,
        )
    except BundleAlignmentError as e:
        # check_bundle_alignment failed structurally (path/branch/etc).
        # Aggregate as a Gate 1 failure with the underlying error name.
        failures.append(GateFailure(
            gate_name="bundle_alignment",
            reason=str(e),
            overridable=False, override_used=False,
            detail={"error_type": type(e).__name__},
        ))
        log.event(
            "gate_failed",
            gate_name="bundle_alignment",
            reason=str(e),
            error_type=type(e).__name__,
        )
        return

    if alignment.aligned:
        log.event(
            "gate_passed",
            gate_name="bundle_alignment",
            bundled_version=alignment.bundled_version,
            dist_version=alignment.dist_version,
            bundled_commit_sha=alignment.bundled_commit_sha,
        )
        return

    # Misaligned. Allow if overridden with a written reason.
    if overrides.bundle_mismatch_reason:
        log.event(
            "gate_passed",
            gate_name="bundle_alignment",
            overridden=True,
            override_reason=overrides.bundle_mismatch_reason,
            bundled_version=alignment.bundled_version,
            dist_version=alignment.dist_version,
            bundled_commit_sha=alignment.bundled_commit_sha,
        )
        return

    failures.append(GateFailure(
        gate_name="bundle_alignment",
        reason=(
            f"Bundle alignment failed.\n"
            f"  bundled (Flutter {alignment.branch} HEAD): {alignment.bundled_version}\n"
            f"  dist (just-built):                          {alignment.dist_version}\n"
            f"  flutter commit: {alignment.bundled_commit_sha}\n"
            "Either commit the new bundle to Flutter main, or pass\n"
            "  --override-bundle-mismatch=\"<written reason>\""
        ),
        overridable=True, override_used=False,
        detail={
            "bundled_version": alignment.bundled_version,
            "dist_version": alignment.dist_version,
            "bundled_commit_sha": alignment.bundled_commit_sha,
            "branch": alignment.branch,
        },
    ))
    log.event(
        "gate_failed",
        gate_name="bundle_alignment",
        bundled_version=alignment.bundled_version,
        dist_version=alignment.dist_version,
        bundled_commit_sha=alignment.bundled_commit_sha,
    )


def _evaluate_gate_2_blast_radius(
    *,
    log: AuditLog,
    would_delete_count: int,
    would_delete_pct: float,
    storage_total: int,
    blast_radius_threshold: float,
    overrides: GateOverrides,
    failures: List[GateFailure],
) -> None:
    """Gate 2: deletion fraction must be ≤ threshold, OR overridden with
    --expected-count exactly matching would_delete_count."""
    if would_delete_pct <= blast_radius_threshold:
        log.event(
            "gate_passed",
            gate_name="blast_radius",
            would_delete_count=would_delete_count,
            storage_total=storage_total,
            pct=would_delete_pct,
            threshold=blast_radius_threshold,
        )
        return

    # Exceeds threshold. Allow only with exact --expected-count match.
    if overrides.expected_count is not None and overrides.expected_count == would_delete_count:
        log.event(
            "gate_passed",
            gate_name="blast_radius",
            overridden=True,
            expected_count=overrides.expected_count,
            actual_count=would_delete_count,
            pct=would_delete_pct,
            threshold=blast_radius_threshold,
        )
        return

    pct_str = f"{would_delete_pct:.2%}"
    threshold_str = f"{blast_radius_threshold:.2%}"
    reason_lines = [
        f"Blast-radius gate failed: would delete {would_delete_count}/{storage_total} blobs ({pct_str})",
        f"  exceeds threshold {threshold_str}.",
    ]
    if overrides.expected_count is not None:
        reason_lines.append(
            f"  --expected-count={overrides.expected_count} does not match actual {would_delete_count}; "
            "the override requires exact match."
        )
    else:
        reason_lines.append(
            f"  Pass --expected-count={would_delete_count} if this large deletion is intentional."
        )

    failures.append(GateFailure(
        gate_name="blast_radius",
        reason="\n".join(reason_lines),
        overridable=True,
        override_used=overrides.expected_count is not None,
        detail={
            "would_delete_count": would_delete_count,
            "storage_total": storage_total,
            "would_delete_pct": would_delete_pct,
            "threshold": blast_radius_threshold,
            "expected_count": overrides.expected_count,
        },
    ))
    log.event(
        "gate_failed",
        gate_name="blast_radius",
        would_delete_count=would_delete_count,
        storage_total=storage_total,
        pct=would_delete_pct,
        threshold=blast_radius_threshold,
        expected_count=overrides.expected_count,
    )


def _short_circuit_failure(
    *,
    log: AuditLog,
    mode: GateMode,
    failure: GateFailure,
) -> GateResult:
    """Build a failed GateResult for a precondition short-circuit."""
    log.event(
        "gate_failed",
        gate_name=failure.gate_name,
        reason=failure.reason,
        **{k: v for k, v in failure.detail.items() if k not in {"reason", "gate_name"}},
    )
    log.event("gate_evaluation_complete", passed=False, failure_count=1,
              failed_gates=[failure.gate_name])
    return GateResult(
        passed=False, mode=mode,
        protected_set=None,
        deletion_candidates=frozenset(),
        would_delete_count=0,
        would_delete_pct=0.0,
        failures=[failure],
        audit_log_path=log.path,
    )
