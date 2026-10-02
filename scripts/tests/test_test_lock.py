"""scripts/test_lock.py: one heavy suite at a time, fast suites share.

2026-10-02: three fast suites ran at once on a 16 GB Mac, swap hit 31 GB and
a 15-minute suite took 50 minutes with ten timeout failures.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

LOCK = Path(__file__).resolve().parents[1] / "test_lock.py"


def _start(tmp_path: Path, mode: str, code: str) -> subprocess.Popen:
    env = dict(os.environ, PG_TEST_LOCK_DIR=str(tmp_path))
    return subprocess.Popen(
        [sys.executable, str(LOCK), mode, "--", sys.executable, "-c", code],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _wait_for_markers(tmp_path: Path, count: int) -> None:
    deadline = time.time() + 10
    while len(list((tmp_path / "runs").glob("*.run"))) < count:
        assert time.time() < deadline, "runs never registered"
        time.sleep(0.05)


def test_shared_compatibility_mode_serializes_runs(tmp_path):
    first = _start(tmp_path, "shared", "import time; time.sleep(.5)")
    _wait_for_markers(tmp_path, 1)
    second = _start(tmp_path, "shared", "print('ran')")
    out, err = second.communicate(timeout=20)
    first.communicate(timeout=20)
    assert out.strip() == "ran"
    assert "waiting for the machine-wide test lock" in err


def test_exclusive_waits_for_a_shared_run(tmp_path):
    holder = _start(tmp_path, "shared", "import time; time.sleep(1.5)")
    _wait_for_markers(tmp_path, 1)
    started = time.time()
    heavy = _start(tmp_path, "exclusive", "print('ran')")
    out, err = heavy.communicate(timeout=20)
    holder.communicate(timeout=20)

    assert out.strip() == "ran"
    assert "waiting for the machine-wide test lock (exclusive)" in err
    assert time.time() - started >= 1.0


def test_dead_run_markers_do_not_count(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "999999.run").write_text("shared pid 999999 in /gone")
    run = _start(tmp_path, "shared", "print('ran')")

    assert run.communicate(timeout=20)[0].strip() == "ran"
    assert not (runs / "999999.run").exists()


def test_the_command_exit_code_is_returned(tmp_path):
    run = _start(tmp_path, "exclusive", "raise SystemExit(3)")
    run.communicate(timeout=20)

    assert run.returncode == 3


def test_shared_mode_cannot_start_another_memory_heavy_run(tmp_path):
    ready, release = tmp_path / 'ready', tmp_path / 'release'
    code = f"from pathlib import Path; import time; Path({str(ready)!r}).touch();\nwhile not Path({str(release)!r}).exists(): time.sleep(.02)"
    first = _start(tmp_path, 'shared', code)
    _wait_for_markers(tmp_path, 1)
    second = _start(tmp_path, 'shared', "print('second')")
    try:
        time.sleep(.2)
        assert second.poll() is None, 'second heavy run overlapped the first'
    finally:
        release.touch()
        first.communicate(timeout=20)
        second.communicate(timeout=20)


def test_lock_survives_wrapper_death_while_child_is_running(tmp_path):
    ready, release = tmp_path / 'child_ready', tmp_path / 'release'
    code = f"from pathlib import Path; import time; Path({str(ready)!r}).touch();\nwhile not Path({str(release)!r}).exists(): time.sleep(.02)"
    first = _start(tmp_path, 'exclusive', code)
    deadline = time.monotonic() + 10
    while not ready.exists():
        assert time.monotonic() < deadline
        time.sleep(.02)
    first.terminate()
    first.wait(timeout=10)
    second = _start(tmp_path, 'exclusive', "print('second')")
    try:
        time.sleep(.2)
        assert second.poll() is None, 'wrapper death released a still-active workload'
    finally:
        release.touch()
        first.communicate(timeout=20)
        second.communicate(timeout=20)
