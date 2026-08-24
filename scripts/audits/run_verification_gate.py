#!/usr/bin/env python3
"""Run one verification command and emit an exit-code/log-bound receipt.

The receipt is written by the same process that observes the child exit code.
Candidate reports consume these receipts instead of trusting hand-authored
``exit_code`` fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


RECEIPT_SCHEMA_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_receipt(path: Path, payload: dict) -> None:
    body = dict(payload)
    body["receipt_sha256"] = _canonical_sha256(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_gate(
    *,
    name: str,
    command: Sequence[str],
    log_path: Path,
    receipt_path: Path,
    cwd: Path,
) -> int:
    """Run ``command`` and return its actual exit code after writing a receipt."""
    if not name.strip():
        raise ValueError("gate name must not be empty")
    if not command:
        raise ValueError("verification command must not be empty")

    cwd = Path(cwd).resolve()
    log_path = Path(log_path).resolve()
    receipt_path = Path(receipt_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    exit_code = 125

    with log_path.open("wb") as log_handle:
        process = subprocess.Popen(
            [str(part) for part in command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        try:
            for chunk in iter(lambda: process.stdout.read(64 * 1024), b""):
                log_handle.write(chunk)
                log_handle.flush()
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            exit_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            exit_code = 130
        finally:
            process.stdout.close()

    payload = {
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "gate_name": name,
        "command": [str(part) for part in command],
        "cwd": str(cwd),
        "started_at": started_at,
        "completed_at": _utc_now(),
        "duration_seconds": round(time.monotonic() - started_monotonic, 3),
        "exit_code": exit_code,
        "log": str(log_path),
        "log_sha256": _sha256(log_path),
    }
    _write_receipt(receipt_path, payload)
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--cwd", default=Path.cwd(), type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    return run_gate(
        name=args.name,
        command=command,
        log_path=args.log,
        receipt_path=args.receipt,
        cwd=args.cwd,
    )


if __name__ == "__main__":
    raise SystemExit(main())
