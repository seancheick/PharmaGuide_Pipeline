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
    env = dict(os.environ, PG_TEST_LOCK_DIR=str(tmp_path), PG_TEST_LOCK_CAPACITY="4")
    return subprocess.Popen(
        [sys.executable, str(LOCK), mode, "--", sys.executable, "-c", code],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _wait_for_markers(tmp_path: Path, count: int) -> None:
    deadline = time.time() + 10
    while len(list((tmp_path / "runs").glob("*.run"))) < count:
        assert time.time() < deadline, "runs never registered"
        time.sleep(0.05)


def test_shared_runs_overlap_and_see_each_other(tmp_path):
    report = "import os,time; time.sleep(1); print(os.environ['PG_TEST_CONCURRENT_RUNS'])"
    first = _start(tmp_path, "shared", report)
    _wait_for_markers(tmp_path, 1)
    second = _start(tmp_path, "shared", report)
    outputs = [p.communicate(timeout=20)[0].strip() for p in (first, second)]

    assert "2" in outputs  # the later run saw both, so it was not blocked


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


def test_a_focused_run_does_not_wait_for_a_heavy_suite(tmp_path):
    # Sean, 2026-10-02: focused checks were queued behind a profiling suite.
    release = tmp_path / "release"
    holder = _start(
        tmp_path, "exclusive",
        f"from pathlib import Path; import time\nwhile not Path({str(release)!r}).exists(): time.sleep(.05)",
    )
    _wait_for_markers(tmp_path, 1)
    repo = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items() if k != "PG_TEST_LOCK_HELD"}
    env["PG_TEST_LOCK_DIR"] = str(tmp_path)
    try:
        focused = subprocess.run(
            ["bash", "scripts/test.sh", "fast", "scripts/tests/test_ci_skip_guard.py"],
            cwd=repo, env=env, capture_output=True, text=True, timeout=120,
        )
    finally:
        release.touch()
        holder.communicate(timeout=20)

    assert focused.returncode == 0, focused.stdout[-2000:] + focused.stderr[-2000:]
    assert "waiting for the machine-wide test lock" not in focused.stderr


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


def test_broad_worker_slots_bound_overlap(tmp_path):
    release = tmp_path / "release_slots"
    code = f"from pathlib import Path; import os,time; print(os.environ['PG_TEST_WORKERS'], flush=True)\nwhile not Path({str(release)!r}).exists(): time.sleep(.02)"
    holders = [_start(tmp_path, "shared", code) for _ in range(3)]
    _wait_for_markers(tmp_path, 3)
    queued = _start(tmp_path, "shared", "import os; print(os.environ['PG_TEST_WORKERS'])")
    try:
        time.sleep(.3)
        assert queued.poll() is None, "fourth broad run exceeded the reserved budget"
    finally:
        release.touch()
        outputs = [p.communicate(timeout=20)[0].strip() for p in holders]
        out, err = queued.communicate(timeout=20)
    assert outputs == ["1"] * 3
    assert out.strip() == "1"
    assert "waiting for a broad-worker slot" in err


def test_exclusive_worker_override_is_capped(tmp_path):
    env = dict(os.environ, PG_TEST_LOCK_DIR=str(tmp_path), PG_TEST_LOCK_CAPACITY="4", PG_TEST_WORKERS="99")
    result = subprocess.run([sys.executable, str(LOCK), "exclusive", "--", sys.executable, "-c", "import os; print(os.environ['PG_TEST_WORKERS'])"], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0
    assert result.stdout.strip() == "3"


def test_cli_worker_override_cannot_bypass_runner_budget():
    repo = Path(__file__).resolve().parents[2]
    for option in ("-n", "-n99", "--numprocesses", "--numprocesses=auto"):
        result = subprocess.run(["bash", "scripts/test.sh", "fast", "scripts/tests/test_ci_skip_guard.py", option], cwd=repo, capture_output=True, text=True, timeout=20)
        assert result.returncode == 2
        assert "worker overrides must use PG_TEST_WORKERS" in result.stderr


def test_focused_worker_budget_overrides_pytest_addopts(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTEST_ADDOPTS="-n 99")
    result = subprocess.run(["bash", "scripts/test.sh", "fast", "scripts/tests/test_ci_skip_guard.py", "-o", "addopts=-n 99"], cwd=repo, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert "bringing up nodes" not in result.stdout
