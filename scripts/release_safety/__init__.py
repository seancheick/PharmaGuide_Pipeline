"""Release-safety primitives for the PharmaGuide pipeline.

This package implements ADR-0001 — Release pipeline safety architecture.
See docs/adr/0001-release-pipeline-safety.md.

Phased rollout (the package grows phase-by-phase):

    P1.1  lock.py              — pipeline release lock         (HR-12)
    P1.2  index_validator.py   — detail_index validation        (HR-11)
    P1.3  bundle_alignment.py  — Flutter main HEAD bundle gate  (HR-13, Gate 1)
    P1.4  protected_blobs.py   — bundled∪dist union (interim)
    P1.5  gates.py             — three-gate orchestrator + audit log
    P1.6  (wire-in to cleanup_old_versions.py)

Each module is independently importable and unit-tested without
network calls or Supabase mocks.
"""

from .lock import (
    ReleaseLock,
    ReleaseLockError,
    LockContentionError,
    StaleLockError,
    CorruptLockError,
    acquire_release_lock,
)
from .index_validator import (
    ValidatedIndex,
    IndexValidationError,
    MalformedJSONError,
    MalformedStructureError,
    MissingFieldError,
    MalformedHashError,
    ChecksumMismatchError,
    validate_detail_index,
)
from .bundle_alignment import (
    BundleManifestSnapshot,
    AlignmentResult,
    BundleAlignmentError,
    FlutterRepoNotFoundError,
    BranchNotFoundError,
    BundleManifestNotFoundError,
    MalformedBundleManifestError,
    BundleMisalignmentError,
    read_flutter_bundle_manifest,
    check_bundle_alignment,
)
from .protected_blobs import (
    ProtectedBlobSet,
    ProtectedBlobSetError,
    MalformedBundleCatalogError,
    BundleCatalogQueryError,
    compute_protected_blob_set,
)
from .audit_log import (
    AuditLog,
    DEFAULT_AUDIT_DIR,
    make_audit_log,
    read_audit_log,
)
from .gates import (
    GateMode,
    GateOverrides,
    GateFailure,
    GateResult,
    DEFAULT_BLAST_RADIUS_THRESHOLD,
    evaluate_cleanup_gates,
)
from .quarantine import (
    QUARANTINE_PREFIX,
    ACTIVE_PREFIX,
    DEFAULT_BUCKET,
    ParsedActivePath,
    ParsedQuarantinePath,
    parse_active_path,
    parse_quarantine_path,
    quarantine_target_path,
    quarantine_blob,
    recover_blob,
    list_quarantine_dates,
)
from .quarantine_sweeper import (
    DEFAULT_QUARANTINE_TTL_DAYS,
    SweepResult,
    is_eligible_for_hard_delete,
    sweep_quarantine,
)
from .storage_audit import (
    DEFAULT_ORPHAN_SAMPLE_SIZE,
    PrefixStats,
    StorageAuditReport,
    run_storage_audit,
)
from .delete_stale_version_dirs import (
    DEFAULT_MANIFEST_TABLE,
    CandidateVersion,
    DeletePlan,
    DeleteResult,
    ExpectedCountMismatch,
    ManifestRaceConditionError,
    compute_delete_plan,
    execute_delete_plan,
    format_plan_text,
)
from .registry import (
    DEFAULT_TABLE as REGISTRY_DEFAULT_TABLE,
    CatalogRelease,
    DuplicateReleaseError,
    IllegalStateTransitionError,
    InvalidReleaseFieldError,
    RegistryError,
    ReleaseChannel,
    ReleaseNotFoundError,
    ReleaseState,
    activate_release,
    get_release,
    insert_pending_release,
    list_active_releases,
    list_releases_by_state,
    retire_release,
    rollback_to_pending,
    transition_to_validating,
)

__all__ = [
    # P1.1 — release lock
    "ReleaseLock",
    "ReleaseLockError",
    "LockContentionError",
    "StaleLockError",
    "CorruptLockError",
    "acquire_release_lock",
    # P1.2 — detail_index validator
    "ValidatedIndex",
    "IndexValidationError",
    "MalformedJSONError",
    "MalformedStructureError",
    "MissingFieldError",
    "MalformedHashError",
    "ChecksumMismatchError",
    "validate_detail_index",
    # P1.3 — bundle alignment (Flutter main HEAD)
    "BundleManifestSnapshot",
    "AlignmentResult",
    "BundleAlignmentError",
    "FlutterRepoNotFoundError",
    "BranchNotFoundError",
    "BundleManifestNotFoundError",
    "MalformedBundleManifestError",
    "BundleMisalignmentError",
    "read_flutter_bundle_manifest",
    "check_bundle_alignment",
    # P1.4 — protected blob set (bundled ∪ dist; interim until P3 registry)
    "ProtectedBlobSet",
    "ProtectedBlobSetError",
    "MalformedBundleCatalogError",
    "BundleCatalogQueryError",
    "compute_protected_blob_set",
    # P1.5a — structured audit log (JSONL, append-only, fsynced)
    "AuditLog",
    "DEFAULT_AUDIT_DIR",
    "make_audit_log",
    "read_audit_log",
    # P1.5b — gates orchestrator
    "GateMode",
    "GateOverrides",
    "GateFailure",
    "GateResult",
    "DEFAULT_BLAST_RADIUS_THRESHOLD",
    "evaluate_cleanup_gates",
    # P2.1a — quarantine primitive (move-to-quarantine + recover)
    "QUARANTINE_PREFIX",
    "ACTIVE_PREFIX",
    "DEFAULT_BUCKET",
    "ParsedActivePath",
    "ParsedQuarantinePath",
    "parse_active_path",
    "parse_quarantine_path",
    "quarantine_target_path",
    "quarantine_blob",
    "recover_blob",
    "list_quarantine_dates",
    # P2.1b — quarantine sweeper (TTL-based hard-delete)
    "DEFAULT_QUARANTINE_TTL_DAYS",
    "SweepResult",
    "is_eligible_for_hard_delete",
    "sweep_quarantine",
    # Storage audit (read-only inventory; P3 prerequisite)
    "DEFAULT_ORPHAN_SAMPLE_SIZE",
    "PrefixStats",
    "StorageAuditReport",
    "run_storage_audit",
    # Bucket-2 cleanup: stale version-directory deletion
    "DEFAULT_MANIFEST_TABLE",
    "CandidateVersion",
    "DeletePlan",
    "DeleteResult",
    "ExpectedCountMismatch",
    "ManifestRaceConditionError",
    "compute_delete_plan",
    "execute_delete_plan",
    "format_plan_text",
    # P3.2 — catalog_releases registry (Python API + state machine)
    "REGISTRY_DEFAULT_TABLE",
    "CatalogRelease",
    "DuplicateReleaseError",
    "IllegalStateTransitionError",
    "InvalidReleaseFieldError",
    "RegistryError",
    "ReleaseChannel",
    "ReleaseNotFoundError",
    "ReleaseState",
    "activate_release",
    "get_release",
    "insert_pending_release",
    "list_active_releases",
    "list_releases_by_state",
    "retire_release",
    "rollback_to_pending",
    "transition_to_validating",
]
