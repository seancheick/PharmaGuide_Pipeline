#!/usr/bin/env python3
"""Machine-wide lock for scripts/test.sh, shared by every worktree.

2026-10-02: three fast suites ran at once on a 16 GB Mac (each sized its
xdist workers as if it were alone), swap hit 31 GB and a 15-minute suite
took 50 minutes with ten timeout failures.

    test_lock.py shared -- <cmd...>     # broad fast/local: bounded one-worker slots
    test_lock.py exclusive -- <cmd...>  # full/release/slow: one, and alone

Focused runs (named test files or nodes) never call this: they must not wait
behind a broad suite (Sean, 2026-10-02). The command gets
PG_TEST_CONCURRENT_RUNS (live locked runs) for diagnostics; slot locks, not that snapshot, bound worker allocation.

The command inherits the lock descriptor, so killing the wrapper does not
release a still-running child workload. The OS releases it after the last holder exits. Run markers name active workloads in waiting diagnostics.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

LOCK_DIR = Path(
    os.environ.get("PG_TEST_LOCK_DIR") or Path.home() / ".cache" / "pharmaguide-tests"
)


def inherited_lock_fds() -> tuple[int, ...]:
    """Validate the lock owner's descriptors before passing them to descendants."""
    declared = os.environ.get('PG_TEST_LOCK_FDS', '')
    if not declared:
        return ()
    try:
        descriptors = tuple(int(value) for value in declared.split(','))
        if len(descriptors) not in (1, 2) or len(set(descriptors)) != len(descriptors):
            return ()
        allowed = { (path.stat().st_dev, path.stat().st_ino)
                    for path in [LOCK_DIR / 'suite.lock', *LOCK_DIR.glob('worker-*.lock')] if path.is_file() }
        suite = (LOCK_DIR / 'suite.lock').stat()
        identities = [(os.fstat(fd).st_dev, os.fstat(fd).st_ino) for fd in descriptors if fd > 2]
        if (len(identities) != len(descriptors) or any(identity not in allowed for identity in identities)
                or identities[0] != (suite.st_dev, suite.st_ino)):
            return ()
        return descriptors
    except (ValueError, OSError):
        return ()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _live_runs(runs_dir: Path) -> list[str]:
    live = []
    for marker in runs_dir.glob("*.run"):
        try:
            pid = int(marker.stem)
        except ValueError:
            continue
        if _pid_alive(pid):
            live.append(marker.read_text(encoding="utf-8").strip())
        else:
            marker.unlink(missing_ok=True)
    return live


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] not in ("shared", "exclusive") or argv[1] != "--":
        print("usage: test_lock.py shared|exclusive -- <command...>", file=sys.stderr)
        return 2
    mode, command = argv[0], argv[2:]
    runs_dir = LOCK_DIR / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    lock_file = (LOCK_DIR / "suite.lock").open("a+")
    flag = fcntl.LOCK_SH if mode == "shared" else fcntl.LOCK_EX
    try:
        fcntl.flock(lock_file, flag | fcntl.LOCK_NB)
    except BlockingIOError:
        holders = _live_runs(runs_dir)
        print(
            f"test.sh: waiting for the machine-wide test lock ({mode}); running: "
            + ("; ".join(holders) or "unknown"),
            file=sys.stderr,
            flush=True,
        )
        fcntl.flock(lock_file, flag)

    # The runner supplies its existing RAM estimate. Keep one worker's
    # headroom for focused checks; broad shared runs each claim one slot.
    capacity = max(1, int(os.environ.get("PG_TEST_LOCK_CAPACITY") or 4))
    broad_capacity = max(1, capacity - 1)
    slot = None
    if mode == "shared":
        waiting = False
        while slot is None:
            for index in range(broad_capacity):
                candidate = (LOCK_DIR / f"worker-{index}.lock").open("a+")
                try:
                    fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    slot = candidate
                    break
                except BlockingIOError:
                    candidate.close()
            if slot is None:
                if not waiting:
                    print("test.sh: waiting for a broad-worker slot; focused checks bypass this queue", file=sys.stderr, flush=True)
                    waiting = True
                time.sleep(.05)

    marker = runs_dir / f"{os.getpid()}.run"
    marker.write_text(f"{mode} pid {os.getpid()} in {os.getcwd()}", encoding="utf-8")
    try:
        workers = 1 if mode == "shared" else min(broad_capacity, max(1, int(os.environ.get("PG_TEST_WORKERS") or broad_capacity)))
        env = dict(os.environ, PG_TEST_CONCURRENT_RUNS=str(len(_live_runs(runs_dir))), PG_TEST_WORKERS=str(workers))
        descriptors = (lock_file.fileno(),) + ((slot.fileno(),) if slot else ())
        env['PG_TEST_LOCK_FDS'] = ','.join(str(fd) for fd in descriptors)
        return subprocess.call(command, env=env, pass_fds=descriptors)
    except KeyboardInterrupt:
        return 130
    finally:
        marker.unlink(missing_ok=True)
        lock_file.close()
        if slot:
            slot.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
