"""The full release and its child commands share one cross-process lock."""

from __future__ import annotations

import importlib.util
import json
import os
import sys


def test_lock_runner_holds_lock_and_passes_borrow_token_to_child(tmp_path):
    spec = importlib.util.find_spec("run_with_release_lock")
    assert spec is not None, "the release needs a lock-owning command runner"

    import run_with_release_lock as runner

    lock_path = tmp_path / "release.lock"
    observed_path = tmp_path / "observed.json"
    child = (
        "import json, os, pathlib; "
        f"p=pathlib.Path({str(observed_path)!r}); "
        f"lock=pathlib.Path({str(lock_path)!r}); "
        "p.write_text(json.dumps({"
        "'lock_exists': lock.exists(), "
        "'has_token': bool(os.environ.get('PG_RELEASE_LOCK_TOKEN')), "
        "'wrapped': os.environ.get('PG_RELEASE_LOCK_WRAPPED')}))"
    )

    exit_code = runner.main([
        "--lock-path", str(lock_path),
        "--", sys.executable, "-c", child,
    ])

    assert exit_code == 0
    observed = json.loads(observed_path.read_text())
    assert observed == {
        "lock_exists": True,
        "has_token": True,
        "wrapped": "1",
    }
    assert not lock_path.exists(), "the wrapper releases after its child exits"


def test_lock_runner_refuses_when_a_live_foreign_holder_exists(tmp_path):
    spec = importlib.util.find_spec("run_with_release_lock")
    assert spec is not None, "the release needs a lock-owning command runner"

    import run_with_release_lock as runner

    lock_path = tmp_path / "release.lock"
    lock_path.write_text(json.dumps({
        "pid": os.getpid(),
        "host": "test",
        "started_at": "2026-08-28T00:00:00+00:00",
        "current_step": "other release",
    }))

    exit_code = runner.main([
        "--lock-path", str(lock_path),
        "--", sys.executable, "-c", "raise SystemExit(99)",
    ])

    assert exit_code != 0
    assert lock_path.exists()


def test_terminating_wrapper_stops_descendants_before_releasing_lock(tmp_path):
    import signal
    import subprocess
    import time
    import run_with_release_lock as runner
    from pathlib import Path
    lock = tmp_path / 'lock'
    ready = tmp_path / 'ready'
    leaked = tmp_path / 'orphan-wrote'
    grandchild = ("import os,time,signal; from pathlib import Path; "
                  "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                  f"Path({str(ready)!r}).write_text(str(os.getpid())); "
                  f"time.sleep(1.5); Path({str(leaked)!r}).write_text('unsafe'); time.sleep(20)")
    child_pid = tmp_path / 'child-pid'
    child = ("import os,subprocess,sys,time; from pathlib import Path; "
             f"Path({str(child_pid)!r}).write_text(str(os.getpid())); "
             f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]); time.sleep(30)")
    process = subprocess.Popen([sys.executable, str(Path(runner.__file__)), '--lock-path', str(lock),
                                '--', sys.executable, '-c', child])
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists() and lock.exists()
        process.terminate()
        process.wait(timeout=12)
        time.sleep(1.7)
        assert not leaked.exists(), 'a descendant kept writing after exclusivity ended'
        assert not lock.exists()
    finally:
        for path in (ready, child_pid):
            if path.exists():
                try:
                    os.kill(int(path.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if process.poll() is None:
            process.kill()
            process.wait()
