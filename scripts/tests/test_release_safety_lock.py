"""Tests for scripts/release_safety/lock.py — pipeline release lock.

ADR-0001 P1.1 — implements HR-12 (single release lock at a time).

All tests are pure unit tests:
  - no Supabase client, no network
  - PID liveness is monkeypatched where the test needs to control it
  - same-process semantics use the actual implementation
  - subprocess + signal-delivery testing is intentionally NOT included
    (per P1.1 sign-off — avoid brittle CI). Signal-handler install/restore
    is covered indirectly by the clean-release and exception-release tests.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Test 1 — acquire on empty path
# ---------------------------------------------------------------------------


def test_p1_1_acquire_on_empty_path_writes_lock_with_metadata(tmp_path):
    """Acquiring a lock at a path with no prior lock writes the JSON file
    with the expected metadata fields and the current PID."""
    from release_safety.lock import acquire_release_lock

    lock_path = tmp_path / ".release.lock"

    with acquire_release_lock(lock_path, initial_step="upload_blobs") as lock:
        assert lock_path.exists()
        data = json.loads(lock_path.read_text())

        assert data["pid"] == os.getpid()
        assert data["host"] == socket.gethostname()
        assert data["current_step"] == "upload_blobs"
        assert "started_at" in data and isinstance(data["started_at"], str)

        # The yielded ReleaseLock exposes the same metadata.
        assert lock.pid == os.getpid()
        assert lock.metadata["current_step"] == "upload_blobs"


# ---------------------------------------------------------------------------
# Test 2 — live-lock contention
# ---------------------------------------------------------------------------


def test_p1_1_live_lock_contention_raises_with_holder_metadata(tmp_path):
    """If a lock file exists with a live PID, acquisition raises
    LockContentionError carrying the holder's diagnostic metadata, and the
    lock file is NOT modified or removed (we don't own it)."""
    from release_safety.lock import acquire_release_lock, LockContentionError

    lock_path = tmp_path / ".release.lock"

    holder_metadata = {
        "pid": os.getpid(),  # this process — definitely alive
        "host": "fake-host",
        "started_at": "2026-05-12T20:00:00+00:00",
        "current_step": "uploading_blobs",
    }
    lock_path.write_text(json.dumps(holder_metadata))

    with pytest.raises(LockContentionError) as excinfo:
        with acquire_release_lock(lock_path):
            pass

    err = excinfo.value
    msg = str(err)
    assert err.holder_metadata == holder_metadata
    assert err.lock_path == lock_path.resolve() or str(lock_path) in msg

    # Diagnostic fields must surface in the message so operators can decide.
    assert str(os.getpid()) in msg
    assert "uploading_blobs" in msg
    assert "fake-host" in msg

    # Lock file must remain untouched — we do not own it.
    assert lock_path.exists()
    assert json.loads(lock_path.read_text()) == holder_metadata


# ---------------------------------------------------------------------------
# Test 3 — stale-lock detection (PID liveness mocked for portability)
# ---------------------------------------------------------------------------


def test_p1_1_stale_lock_detection_raises_with_cleanup_command(tmp_path, monkeypatch):
    """If a lock file exists but the holder PID is dead, acquisition raises
    StaleLockError. The lock is NOT auto-cleared. The error message includes
    the exact cleanup command (per the no-interactive-prompt design)."""
    from release_safety import lock as lock_mod
    from release_safety.lock import acquire_release_lock, StaleLockError

    lock_path = tmp_path / ".release.lock"

    holder_metadata = {
        "pid": 424242,  # arbitrary; the mock will report it dead
        "host": "old-host",
        "started_at": "2026-05-11T03:14:15+00:00",
        "current_step": "orphan_cleanup",
    }
    lock_path.write_text(json.dumps(holder_metadata))

    # Mock _is_pid_alive to report the holder as dead.
    monkeypatch.setattr(lock_mod, "_is_pid_alive", lambda pid: False)

    with pytest.raises(StaleLockError) as excinfo:
        with acquire_release_lock(lock_path):
            pass

    err = excinfo.value
    msg = str(err)
    assert err.holder_metadata == holder_metadata

    # Diagnostic + actionable fields in the message.
    assert "424242" in msg
    assert "orphan_cleanup" in msg
    assert f"rm {lock_path.resolve()}" in msg or f"rm {lock_path}" in msg

    # NO auto-clear — file must still exist with original contents.
    assert lock_path.exists()
    assert json.loads(lock_path.read_text()) == holder_metadata


# ---------------------------------------------------------------------------
# Test 4 — clean release removes lock
# ---------------------------------------------------------------------------


def test_p1_1_clean_release_removes_lock(tmp_path):
    """Exiting the context manager normally removes the lock file."""
    from release_safety.lock import acquire_release_lock

    lock_path = tmp_path / ".release.lock"

    with acquire_release_lock(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


# ---------------------------------------------------------------------------
# Test 5 — exception release removes lock
# ---------------------------------------------------------------------------


def test_p1_1_exception_release_removes_lock(tmp_path):
    """An exception inside the with-block still releases the lock; the
    exception propagates."""
    from release_safety.lock import acquire_release_lock

    lock_path = tmp_path / ".release.lock"

    class _Sentinel(Exception):
        pass

    with pytest.raises(_Sentinel):
        with acquire_release_lock(lock_path):
            assert lock_path.exists()
            raise _Sentinel("boom")

    assert not lock_path.exists()


# ---------------------------------------------------------------------------
# Test 6 — same-process re-entry is idempotent
# ---------------------------------------------------------------------------


def test_p1_1_same_process_reentry_is_idempotent(tmp_path):
    """Re-entering the lock from the same PID returns the same ReleaseLock
    object; the inner __exit__ does NOT release the lock; the outer __exit__
    does."""
    from release_safety.lock import acquire_release_lock

    lock_path = tmp_path / ".release.lock"

    with acquire_release_lock(lock_path) as outer:
        with acquire_release_lock(lock_path) as inner:
            assert inner is outer
            assert lock_path.exists()
        # Inner __exit__ ran — lock must STILL exist.
        assert lock_path.exists()

    # Outer __exit__ released the lock.
    assert not lock_path.exists()


# ---------------------------------------------------------------------------
# Test 7 — step() updates current_step on disk
# ---------------------------------------------------------------------------


def test_p1_1_step_update_writes_to_lock_file(tmp_path):
    """lock.step(name) updates the on-disk current_step field so a contending
    process gets the right diagnostic in its error message."""
    from release_safety.lock import acquire_release_lock

    lock_path = tmp_path / ".release.lock"

    with acquire_release_lock(lock_path, initial_step="init") as lock:
        assert json.loads(lock_path.read_text())["current_step"] == "init"

        lock.step("uploading_blobs")
        assert json.loads(lock_path.read_text())["current_step"] == "uploading_blobs"

        lock.step("orphan_cleanup")
        assert json.loads(lock_path.read_text())["current_step"] == "orphan_cleanup"


# ---------------------------------------------------------------------------
# Test 8 — corrupt lock file fails closed (P1.1 added per ADR HR-9 / sign-off)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contents,scenario",
    [
        ("THIS IS NOT VALID JSON {{{",                        "invalid_json"),
        ('"a json string but not an object"',                 "wrong_root_type"),
        ('{"host": "h", "started_at": "2026-05-12"}',         "missing_pid"),
        ('{"pid": "not-an-int", "host": "h"}',                "wrong_type_pid"),
        ('{"pid": null}',                                     "null_pid"),
    ],
)
def test_p1_1_corrupt_lock_file_fails_closed(tmp_path, contents, scenario):
    """Any unparseable or malformed lock file raises CorruptLockError.
    The file is NEVER auto-overwritten or deleted (fail closed). The error
    message includes the manual cleanup instruction.

    Scenarios cover: invalid JSON, wrong root type (non-object), missing
    pid field, wrong-type pid, null pid. All must converge on the same
    fail-closed behavior — anything we can't make a liveness decision from
    is corrupt by definition.
    """
    from release_safety.lock import acquire_release_lock, CorruptLockError

    lock_path = tmp_path / ".release.lock"
    lock_path.write_text(contents)

    with pytest.raises(CorruptLockError) as excinfo:
        with acquire_release_lock(lock_path):
            pass

    err = excinfo.value
    msg = str(err)
    assert err.lock_path == lock_path
    assert "CORRUPT" in msg
    # Cleanup instruction must be in the message — operator-actionable.
    assert f"rm {lock_path}" in msg or f"rm {lock_path.resolve()}" in msg

    # File MUST be untouched — fail closed, no silent overwrite.
    assert lock_path.exists()
    assert lock_path.read_text() == contents, (
        f"P1.1 fail-closed breach (scenario={scenario}): corrupt lock file was modified."
    )
