"""Pipeline release lock — JSON-file mutex for state-mutating operations.

Implements ADR-0001 HR-12: only one release or cleanup operation may hold
the pipeline release lock at a time. Read-only operations (dry-run cleanup,
audit-log queries, verify-bundle) do not require the lock.

Design constraints (from ADR-0001 + P1.1 sign-off):
  - No interactive prompting. Errors carry the exact cleanup command/instruction
    in their message; the operator decides what to do. Interactive UX belongs
    in a CLI wrapper, not in the safety primitive.
  - No auto-clear of stale or corrupt locks. Fail closed; require human review.
  - Same-process re-entry is idempotent (inner __exit__ does NOT release the
    outer lock).
  - Lock file is removed on both clean exit AND exception exit.
  - Atomic on-disk update (write to .tmp + fsync + rename) so a partial write
    cannot leave a half-formed lock file behind.

Lock file schema (JSON):
    {
      "pid":          int,        # holder process PID
      "host":         str,        # holder hostname (socket.gethostname)
      "started_at":   str,        # ISO-8601 UTC timestamp of acquisition
      "current_step": str,        # operator-updated diagnostic step name
      "owner_token_sha256": str,  # optional; permits authenticated children
    }
"""

from __future__ import annotations

import errno
import hashlib
import hmac
import json
import os
import signal
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Default lock path — sibling of release_full.sh in scripts/.
# Operators can override via the ``lock_path`` parameter.
# ---------------------------------------------------------------------------

DEFAULT_LOCK_PATH = Path(__file__).resolve().parent.parent / ".release.lock"


# ---------------------------------------------------------------------------
# Exception hierarchy — all errors carry actionable remediation in the message.
# ---------------------------------------------------------------------------


class ReleaseLockError(Exception):
    """Base class for all release-lock failures.

    Catch this to handle any lock acquisition failure generically.
    Catch a specific subclass when the response should differ by reason.
    """


class LockContentionError(ReleaseLockError):
    """Another live process holds the release lock.

    The holder is identified by a process whose PID is currently running
    on this host. Recovery: wait for the holder to finish, or kill it
    (after confirming it's actually our pipeline) before retrying.
    """

    def __init__(self, holder_metadata: dict, lock_path: Path):
        self.holder_metadata = dict(holder_metadata)
        self.lock_path = lock_path
        super().__init__(_format_contention_message(holder_metadata, lock_path))


class StaleLockError(ReleaseLockError):
    """Lock file exists but the holder PID is no longer alive.

    Usually means a previous run crashed without releasing the lock. We
    refuse to auto-clear because:
      - the holder may have been doing partial state-mutating work that
        left the system in an inconsistent state — the operator should
        confirm before resuming
      - auto-clear races with a slow-starting legitimate holder

    Recovery instruction is included in the error message.
    """

    def __init__(self, holder_metadata: dict, lock_path: Path):
        self.holder_metadata = dict(holder_metadata)
        self.lock_path = lock_path
        super().__init__(_format_stale_message(holder_metadata, lock_path))


class CorruptLockError(ReleaseLockError):
    """Lock file exists but cannot be parsed as a valid lock record.

    Failing closed: a corrupt lock file might mean
      - a previous run crashed mid-write (atomic-write should prevent this,
        but filesystem-level corruption can still happen),
      - a manual edit went wrong,
      - or genuine filesystem corruption.

    We refuse to overwrite or delete the file automatically. Recovery
    instruction is included in the error message.
    """

    def __init__(self, lock_path: Path, parse_error: Exception):
        self.lock_path = lock_path
        self.parse_error = parse_error
        super().__init__(_format_corrupt_message(lock_path, parse_error))


# ---------------------------------------------------------------------------
# Error message formatters — kept as pure functions for testability and so the
# constructors stay focused on attribute storage.
# ---------------------------------------------------------------------------


def _format_contention_message(holder: dict, lock_path: Path) -> str:
    return (
        "Pipeline release lock is held by another live process.\n"
        f"  lock file:    {lock_path}\n"
        f"  pid:          {holder.get('pid')}\n"
        f"  host:         {holder.get('host')}\n"
        f"  started_at:   {holder.get('started_at')}\n"
        f"  current_step: {holder.get('current_step', '(unknown)')}\n"
        "\n"
        "Wait for that process to finish, or stop it before retrying."
    )


def _format_stale_message(holder: dict, lock_path: Path) -> str:
    return (
        "Pipeline release lock is STALE — the holder process is no longer running.\n"
        f"  lock file:    {lock_path}\n"
        f"  pid:          {holder.get('pid')}  (no longer running)\n"
        f"  host:         {holder.get('host')}\n"
        f"  started_at:   {holder.get('started_at')}\n"
        f"  current_step: {holder.get('current_step', '(unknown)')}\n"
        "\n"
        "This usually means the previous run crashed without releasing the lock.\n"
        "Inspect recent pipeline logs to confirm there is no in-progress work,\n"
        "then clear the stale lock manually:\n"
        "\n"
        f"  rm {lock_path}\n"
        "\n"
        "Then retry your release."
    )


def _format_corrupt_message(lock_path: Path, parse_error: Exception) -> str:
    return (
        "Pipeline release lock file is CORRUPT and cannot be parsed.\n"
        f"  lock file: {lock_path}\n"
        f"  error:     {type(parse_error).__name__}: {parse_error}\n"
        "\n"
        "Possible causes:\n"
        "  - a previous run crashed mid-write to the lock file\n"
        "  - the file was edited by hand\n"
        "  - filesystem corruption\n"
        "\n"
        "Refusing to overwrite or delete it automatically. Inspect the file\n"
        "contents, confirm no in-progress release, then clear it manually:\n"
        "\n"
        f"  rm {lock_path}\n"
    )


# ---------------------------------------------------------------------------
# PID liveness check — split out for monkeypatch-based testing.
# ---------------------------------------------------------------------------


def _is_pid_alive(pid: int) -> bool:
    """Return True if a process with this PID is alive on this host.

    Uses ``os.kill(pid, 0)`` — sends signal 0, which performs error checking
    without actually delivering a signal. PermissionError means the process
    exists but we lack permission to signal it (still alive).
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as e:
        if e.errno == errno.ESRCH:
            return False
        raise
    return True


# ---------------------------------------------------------------------------
# Atomic lock-file I/O.
# ---------------------------------------------------------------------------


def _read_lock_file(lock_path: Path) -> dict:
    """Read and parse the lock file. Raises CorruptLockError on any parse failure.

    Validates that the parsed payload is a dict with an integer ``pid`` field —
    a payload without these is treated as corrupt (cannot make a liveness
    decision without a PID).
    """
    try:
        with open(lock_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        raise CorruptLockError(lock_path, e) from e

    if not isinstance(data, dict):
        raise CorruptLockError(
            lock_path, ValueError(f"lock payload is not a JSON object: {type(data).__name__}")
        )

    pid = data.get("pid")
    if not isinstance(pid, int):
        raise CorruptLockError(
            lock_path, ValueError(f"lock payload missing or invalid 'pid' field: {pid!r}")
        )

    return data


def _write_lock_file(lock_path: Path, metadata: dict) -> None:
    """Write the lock file atomically: write to .tmp, fsync, rename into place."""
    tmp_path = lock_path.with_suffix(lock_path.suffix + ".tmp")
    with open(tmp_path, "w") as f:
        json.dump(metadata, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, lock_path)


def _create_lock_file_exclusive(lock_path: Path, metadata: dict) -> None:
    """Create a new lock atomically, refusing to replace an existing owner.

    ``exists()`` followed by ``os.replace()`` is not a mutex: two processes
    can both observe absence and then replace one another's lock. ``O_EXCL``
    makes the filesystem choose exactly one winner. A crash during this first
    write may leave a partial file, which is intentionally fail-closed as a
    corrupt lock requiring operator review.
    """
    descriptor = os.open(
        lock_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w") as handle:
            descriptor = -1
            json.dump(metadata, handle)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# Module-level state to track same-process re-entry. Maps the resolved lock
# path string to the ReleaseLock object held by THIS process.
_HELD_BY_THIS_PROCESS: dict = {}


class ReleaseLock:
    """Active release lock, returned from the ``acquire_release_lock`` context.

    Usage::

        with acquire_release_lock() as lock:
            lock.step("upload_blobs")
            ...
            lock.step("orphan_cleanup")
            ...
    """

    def __init__(self, lock_path: Path, metadata: dict):
        self.lock_path = lock_path
        self._metadata = dict(metadata)
        self._owner_pid = metadata["pid"]
        self._signal_handlers_installed = False
        self._previous_handlers: dict = {}

    @property
    def pid(self) -> int:
        """PID of the outer process that owns the on-disk lock."""
        return self._owner_pid

    @property
    def metadata(self) -> dict:
        """Snapshot of the lock's on-disk metadata."""
        return dict(self._metadata)

    def step(self, current_step: str) -> None:
        """Update the lock file's ``current_step`` field.

        Useful for diagnostics: if another process attempts acquisition
        while this lock is held, the contention error message names the
        active step, helping the operator decide whether to wait or kill.
        """
        self._metadata["current_step"] = current_step
        _write_lock_file(self.lock_path, self._metadata)

    # -- internal -----------------------------------------------------------

    def _install_signal_handlers(self) -> None:
        """Install SIGINT/SIGTERM handlers that release the lock then re-raise.

        Best-effort: if we are not in the main thread (signal handlers can
        only be installed there), we skip silently. Clean exit and exception
        exit still release the lock via ``__exit__``.
        """
        if self._signal_handlers_installed:
            return
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._previous_handlers[sig] = signal.signal(sig, self._signal_release)
            except ValueError:
                # Not in main thread; skip.
                pass
        self._signal_handlers_installed = True

    def _restore_signal_handlers(self) -> None:
        for sig, handler in self._previous_handlers.items():
            try:
                signal.signal(sig, handler)
            except ValueError:
                pass
        self._previous_handlers.clear()
        self._signal_handlers_installed = False

    def _signal_release(self, signum, frame):
        self._release()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def _release(self) -> None:
        """Remove the lock file. Idempotent (no-op if already gone)."""
        try:
            os.remove(self.lock_path)
        except FileNotFoundError:
            pass


def acquire_release_lock(
    lock_path: Optional[Path] = None,
    initial_step: str = "starting",
    ownership_token: Optional[str] = None,
) -> "_ReleaseLockContext":
    """Acquire the pipeline release lock.

    Returns a context manager. Same-process re-entry is allowed and idempotent:
    a nested ``with acquire_release_lock(...)`` from the same PID returns the
    already-held lock; the inner ``__exit__`` does NOT release it.

    Args:
        lock_path: path to the lock file. Defaults to ``DEFAULT_LOCK_PATH``.
        initial_step: value written into ``current_step`` on first acquisition.
            For re-entry, the existing ``current_step`` is preserved.
        ownership_token: optional secret held by a wrapper process and passed
            only through the environment to its child commands. Only its
            SHA-256 digest is written to the lock file. This enables safe
            cross-process re-entry while the wrapper remains the sole owner.

    Raises (on context-manager entry):
        LockContentionError: another live process holds the lock.
        StaleLockError: lock file exists but the holder PID is gone.
        CorruptLockError: lock file exists but cannot be parsed.
    """
    if lock_path is None:
        lock_path = DEFAULT_LOCK_PATH
    return _ReleaseLockContext(
        Path(lock_path), initial_step, ownership_token=ownership_token,
    )


class _ReleaseLockContext:
    """Context manager returned from :func:`acquire_release_lock`.

    Kept private — operators interact with it as a context manager (``with ...``)
    and the yielded :class:`ReleaseLock`. Tracking same-process re-entry is
    handled in ``__enter__``/``__exit__`` via the module-level
    ``_HELD_BY_THIS_PROCESS`` dict.
    """

    def __init__(self, lock_path: Path, initial_step: str, *, ownership_token=None):
        # Normalize the path so re-entry detection works regardless of how the
        # caller spelled it (relative vs absolute, with/without trailing dots).
        self.lock_path = Path(os.path.abspath(str(lock_path)))
        self.initial_step = initial_step
        self.ownership_token = ownership_token
        self._lock: Optional[ReleaseLock] = None
        self._is_outer = False

    def __enter__(self) -> ReleaseLock:
        key = str(self.lock_path)

        # Same-process re-entry: return the existing lock unchanged.
        if key in _HELD_BY_THIS_PROCESS:
            self._lock = _HELD_BY_THIS_PROCESS[key]
            self._is_outer = False
            return self._lock

        # Acquire with O_EXCL — checking existence before writing would allow
        # two simultaneous processes to both believe they own the mutex.
        metadata = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "current_step": self.initial_step,
        }
        if self.ownership_token:
            metadata["owner_token_sha256"] = hashlib.sha256(
                self.ownership_token.encode()
            ).hexdigest()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                _create_lock_file_exclusive(self.lock_path, metadata)
                break
            except FileExistsError:
                try:
                    holder = _read_lock_file(self.lock_path)
                except FileNotFoundError:
                    # The previous owner released between O_EXCL and read.
                    # Retry the atomic create rather than treating that
                    # harmless race as a corrupt lock.
                    continue
                if _is_pid_alive(holder["pid"]):
                    inherited_token = os.environ.get("PG_RELEASE_LOCK_TOKEN")
                    expected_digest = holder.get("owner_token_sha256")
                    if (
                        isinstance(inherited_token, str)
                        and inherited_token
                        and isinstance(expected_digest, str)
                        and hmac.compare_digest(
                            hashlib.sha256(inherited_token.encode()).hexdigest(),
                            expected_digest,
                        )
                    ):
                        self._lock = ReleaseLock(self.lock_path, holder)
                        self._is_outer = False
                        return self._lock
                    raise LockContentionError(holder, self.lock_path)
                raise StaleLockError(holder, self.lock_path)

        lock = ReleaseLock(self.lock_path, metadata)
        lock._install_signal_handlers()
        _HELD_BY_THIS_PROCESS[key] = lock
        self._lock = lock
        self._is_outer = True
        return lock

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Inner re-entry exit: do nothing; the outer context owns release.
        if not self._is_outer:
            return False
        if self._lock is None:
            return False

        key = str(self.lock_path)
        try:
            self._lock._restore_signal_handlers()
            self._lock._release()
        finally:
            _HELD_BY_THIS_PROCESS.pop(key, None)
            self._lock = None
        return False  # re-raise any exception from the with-block
