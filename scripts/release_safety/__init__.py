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

__all__ = [
    "ReleaseLock",
    "ReleaseLockError",
    "LockContentionError",
    "StaleLockError",
    "CorruptLockError",
    "acquire_release_lock",
]
