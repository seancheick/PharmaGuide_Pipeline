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
import pytest

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


def test_preparation_child_retains_lock_after_preparation_owner_dies(tmp_path):
    import signal
    ready, release = tmp_path / 'validator_ready', tmp_path / 'release_validator'
    child_code = f"import os,time; from pathlib import Path; Path({str(ready)!r}).write_text(str(os.getppid()));\nwhile not Path({str(release)!r}).exists(): time.sleep(.02)"
    scripts = Path(__file__).resolve().parents[1]
    code = (f"import sys; sys.path.insert(0, {str(scripts)!r}); import preflight; "
            "preflight._preparation_inputs=lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1}; "
            f"preflight.run_preparation({str(tmp_path)!r}, {str(tmp_path)!r}, checks=[{{'name':'validator','command':[sys.executable,'-c',{child_code!r}]}}])")
    first = _start(tmp_path, 'exclusive', code)
    second = None
    try:
        deadline = time.monotonic() + 10
        while not ready.exists():
            assert first.poll() is None
            assert time.monotonic() < deadline
            time.sleep(.02)
        os.kill(int(ready.read_text()), signal.SIGTERM)
        first.wait(timeout=10)
        second = _start(tmp_path, 'exclusive', "print('second')")
        time.sleep(.3)
        assert second.poll() is None, 'Preparation owner death released a still-running validator lock'
    finally:
        release.touch()
        first.communicate(timeout=20)
        if second:
            second.communicate(timeout=20)


def test_inherited_lock_descriptors_require_existing_owner_files(tmp_path, monkeypatch):
    import test_lock
    monkeypatch.setattr(test_lock, 'LOCK_DIR', tmp_path)
    suite = (tmp_path / 'suite.lock').open('a+')
    unrelated = (tmp_path / 'unrelated').open('a+')
    monkeypatch.setattr(test_lock.fcntl, 'flock', lambda *args: pytest.fail('Generic propagation must not upgrade the enclosing suite'))
    try:
        monkeypatch.setenv('PG_TEST_LOCK_FDS', str(suite.fileno()))
        assert test_lock.inherited_lock_fds() == (suite.fileno(),)
        for declaration in ['not-a-descriptor', '0', str(unrelated.fileno()), '999999', f'{suite.fileno()},{suite.fileno()}']:
            monkeypatch.setenv('PG_TEST_LOCK_FDS', declaration)
            assert test_lock.inherited_lock_fds() == ()
    finally:
        suite.close()
        unrelated.close()


def test_preparation_runner_reacquires_with_stale_held_environment(tmp_path):
    release = tmp_path / 'release_stale_flag'
    holder = _start(tmp_path, 'exclusive', f"from pathlib import Path; import time\nwhile not Path({str(release)!r}).exists(): time.sleep(.02)")
    _wait_for_markers(tmp_path, 1)
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PG_TEST_LOCK_DIR=str(tmp_path), PG_TEST_LOCK_HELD='1',
               PG_TEST_LOCK_FDS='999999', PG_PREPARATION_REPORT=str(tmp_path / 'evidence.json'))
    queued = subprocess.Popen(['bash', 'scripts/test.sh', 'preparation', '--collect-only',
                              'scripts/tests/test_ci_skip_guard.py::test_every_local_only_file_exists'],
                             cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(.4)
        assert queued.poll() is None, 'Stale held flag bypassed preparation suite lock'
    finally:
        release.touch()
        holder.communicate(timeout=20)
        out, err = queued.communicate(timeout=30)
    assert queued.returncode == 0, out[-2000:] + err[-2000:]
    assert 'waiting for the machine-wide test lock' in err


@pytest.mark.parametrize('inherited_state', ['shared', 'opened_unlocked'])
@pytest.mark.parametrize('entrypoint', ['cli', 'runner'])
def test_preparation_acquires_exclusive_on_inherited_descriptor(tmp_path, inherited_state, entrypoint):
    ready, release = tmp_path / 'exclusive_validator_ready', tmp_path / 'release_validator'
    release_shared = tmp_path / 'release_shared'
    holder = _start(tmp_path, 'shared', f"from pathlib import Path; import time\nwhile not Path({str(release_shared)!r}).exists(): time.sleep(.02)")
    _wait_for_markers(tmp_path, 1)
    child_code = f"from pathlib import Path; import time; Path({str(ready)!r}).touch();\nwhile not Path({str(release)!r}).exists(): time.sleep(.02)"
    scripts = Path(__file__).resolve().parents[1]
    code = (f"import sys; sys.path.insert(0, {str(scripts)!r}); import preflight; "
            "preflight._preparation_inputs=lambda *args, **kwargs: {'files': {}, 'errors': [], 'raw_count': 1}; "
            "original=preflight.run_preparation; "
            f"preflight.run_preparation=lambda *args, **kwargs: original({str(tmp_path)!r}, {str(tmp_path)!r}, checks=[{{'name':'validator','command':[sys.executable,'-c',{child_code!r}]}}]); "
            f"sys.argv=['preflight.py','--prepare','--raw-root',{str(tmp_path)!r},'--report',{str(tmp_path / 'report.json')!r}]; preflight.main()")
    if entrypoint == 'runner':
        probe = tmp_path / 'test_preparation_probe.py'
        probe.write_text(f"def test_probe():\n    from pathlib import Path\n    import time\n    Path({str(ready)!r}).touch()\n    while not Path({str(release)!r}).exists(): time.sleep(.02)\n")
        code = ("import os; os.environ['PG_TEST_LOCK_HELD']='1'; "
                f"os.environ['PG_PREPARATION_REPORT']={str(tmp_path / 'evidence.json')!r}; "
                f"os.execv('/bin/bash',['bash',{str(scripts / 'test.sh')!r},'preparation',{str(probe)!r}])")
    suite = None
    if inherited_state == 'shared':
        preparation = _start(tmp_path, 'shared', code)
    else:
        suite = (tmp_path / 'suite.lock').open('a+')
        env = dict(os.environ, PG_TEST_LOCK_DIR=str(tmp_path), PG_TEST_LOCK_FDS=str(suite.fileno()))
        preparation = subprocess.Popen([sys.executable, '-c', code], env=env,
            pass_fds=(suite.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    newcomer = None
    try:
        time.sleep(.7)
        assert not ready.exists(), 'Preparation overlapped an existing shared workload'
        release_shared.touch()
        holder.communicate(timeout=20)
        deadline = time.monotonic() + 10
        while not ready.exists():
            assert preparation.poll() is None
            assert time.monotonic() < deadline, 'Inherited lock upgrade deadlocked'
            time.sleep(.02)
        newcomer = _start(tmp_path, 'shared', "print('newcomer')")
        time.sleep(.3)
        assert newcomer.poll() is None, 'Preparation did not retain an exclusive lock'
    finally:
        release_shared.touch()
        release.touch()
        holder.communicate(timeout=20)
        preparation.communicate(timeout=20)
        if suite:
            suite.close()
        if newcomer:
            newcomer.communicate(timeout=20)


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
