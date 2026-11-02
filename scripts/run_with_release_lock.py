#!/usr/bin/env python3
"""Run one state-mutating command while owning the pipeline release lock."""

from __future__ import annotations

import argparse
import os
import secrets
import signal
import subprocess
import sys
from pathlib import Path

from release_safety.lock import ReleaseLockError, acquire_release_lock


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock-path", type=Path, default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        print("[refused] no command supplied after --", file=sys.stderr)
        return 2

    token = secrets.token_hex(32)
    try:
        with acquire_release_lock(
            args.lock_path,
            initial_step=f"running {Path(command[0]).name}",
            ownership_token=token,
        ):
            child_env = os.environ.copy()
            child_env["PG_RELEASE_LOCK_TOKEN"] = token
            child_env["PG_RELEASE_LOCK_WRAPPED"] = "1"
            process = None
            pending_signal = None

            def stop_children(signum, frame):
                nonlocal pending_signal
                pending_signal = signum
                if process is None:
                    return  # A signal during launch is handled immediately after Popen.
                try:
                    os.killpg(process.pid, signum)
                except ProcessLookupError:
                    pass

            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, stop_children)
            if pending_signal is not None:
                return 128 + pending_signal
            process = subprocess.Popen(command, env=child_env, start_new_session=True)
            if pending_signal is not None:
                stop_children(pending_signal, None)
            while pending_signal is None:
                try:
                    result = process.wait(timeout=0.25)
                    if pending_signal is None:
                        return result
                except subprocess.TimeoutExpired:
                    pass
            # Never wait inside a signal handler: it may interrupt wait() while
            # subprocess holds its non-reentrant waitpid lock.
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            finally:
                # A child shell can exit before its grandchildren. Stop the
                # remaining owned group before releasing the release lock.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            return 128 + pending_signal
    except ReleaseLockError as exc:
        print(f"[refused] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
