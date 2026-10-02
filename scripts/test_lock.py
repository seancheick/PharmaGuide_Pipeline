#!/usr/bin/env python3
"""Machine-wide lock for scripts/test.sh, shared by every worktree; one active test workload.

2026-10-02: three fast suites ran at once on a 16 GB Mac (each sized its
xdist workers as if it were alone), swap hit 31 GB and a 15-minute suite
took 50 minutes with ten timeout failures.

    test_lock.py shared -- <cmd...>     # accepted old spelling; still exclusive
    test_lock.py exclusive -- <cmd...>  # all profiles: one workload at a time

The command inherits the lock descriptor, so killing the wrapper does not
release a still-running child workload. The OS releases it after the last holder exits. Run markers name active workloads in waiting diagnostics.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from pathlib import Path

LOCK_DIR = Path(
    os.environ.get("PG_TEST_LOCK_DIR") or Path.home() / ".cache" / "pharmaguide-tests"
)


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
    flag = fcntl.LOCK_EX  # Every run can load the enricher; serialize machine-wide.
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

    _live_runs(runs_dir)  # Clean dead diagnostics after acquiring exclusive ownership.
    marker = runs_dir / f"{os.getpid()}.run"
    marker.write_text(f"{mode} pid {os.getpid()} in {os.getcwd()}", encoding="utf-8")
    try:
        env = dict(os.environ)
        return subprocess.call(command, env=env, pass_fds=(lock_file.fileno(),))
    except KeyboardInterrupt:
        return 130
    finally:
        marker.unlink(missing_ok=True)
        lock_file.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
