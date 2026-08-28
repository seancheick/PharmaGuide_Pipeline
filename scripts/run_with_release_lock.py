#!/usr/bin/env python3
"""Run one state-mutating command while owning the pipeline release lock."""

from __future__ import annotations

import argparse
import os
import secrets
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
            return subprocess.run(command, env=child_env, check=False).returncode
    except ReleaseLockError as exc:
        print(f"[refused] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
