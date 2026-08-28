#!/usr/bin/env python3
"""Restore one quarantined detail blob and prove byte-identical recovery."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_loader  # noqa: F401,E402

from release_safety.lock import ReleaseLockError, acquire_release_lock  # noqa: E402
from release_safety.quarantine import (  # noqa: E402
    _object_exists,
    recover_blob,
)

BUCKET = "pharmaguide"
ACTIVE_ROOT = "shared/details/sha256"
QUARANTINE_ROOT = "shared/quarantine"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blob-hash", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--quarantine-date", required=True)
    parser.add_argument("--bucket", default=BUCKET)
    parser.add_argument("--lock-path", type=Path, default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Restore after the read-only byte check. Without this flag, verify only.",
    )
    return parser


def _validate_args(args) -> str | None:
    if not HASH_RE.fullmatch(args.blob_hash):
        return "--blob-hash must be 64-char lowercase hex"
    if not HASH_RE.fullmatch(args.expected_sha256):
        return "--expected-sha256 must be 64-char lowercase hex"
    if args.expected_sha256 != args.blob_hash:
        return "--expected-sha256 must exactly match --blob-hash"
    try:
        parsed = datetime.strptime(args.quarantine_date, "%Y-%m-%d")
    except ValueError:
        return "--quarantine-date must be a real ISO YYYY-MM-DD date"
    if parsed.strftime("%Y-%m-%d") != args.quarantine_date:
        return "--quarantine-date must be a real ISO YYYY-MM-DD date"
    return None


def _download(client, bucket, path) -> bytes:
    payload = client.storage.from_(bucket).download(path)
    if not isinstance(payload, (bytes, bytearray)):
        raise RuntimeError(f"download returned {type(payload).__name__}, not bytes")
    return bytes(payload)


def _verify_payload(payload: bytes, expected_sha256: str, *, path: str) -> None:
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected_sha256:
        raise RuntimeError(
            f"byte verification failed for {path}: {observed} != {expected_sha256}"
        )


def main(argv=None, *, client=None) -> int:
    args = build_parser().parse_args(argv)
    invalid = _validate_args(args)
    if invalid:
        print(f"[refused] {invalid}")
        return 2

    if client is None:
        from supabase_client import get_supabase_client
        try:
            client = get_supabase_client()
        except ValueError as exc:
            print(f"[error] cannot connect to Supabase: {exc}")
            return 1

    blob_hash = args.blob_hash
    shard = blob_hash[:2]
    leaf = f"{blob_hash}.json"
    quarantine_path = (
        f"{QUARANTINE_ROOT}/{args.quarantine_date}/{shard}/{leaf}"
    )
    active_path = f"{ACTIVE_ROOT}/{shard}/{leaf}"

    def _preflight() -> bytes:
        payload = _download(client, args.bucket, quarantine_path)
        _verify_payload(payload, args.expected_sha256, path=quarantine_path)
        return payload

    if not args.execute:
        try:
            _preflight()
        except Exception as exc:  # noqa: BLE001 — operator-readable refusal.
            print(f"[failed] {type(exc).__name__}: {exc}")
            return 1
        print("Verified quarantine bytes. Dry run only; nothing restored.")
        return 0

    try:
        with acquire_release_lock(
            args.lock_path, initial_step="recover_quarantined_canary",
        ):
            before = _preflight()
            ok, error = recover_blob(
                client,
                blob_hash,
                search_dates=[args.quarantine_date],
                quarantine_root=QUARANTINE_ROOT,
                active_root=ACTIVE_ROOT,
                bucket=args.bucket,
            )
            if not ok:
                raise RuntimeError(error or "recovery failed")
            after = _download(client, args.bucket, active_path)
            _verify_payload(after, args.expected_sha256, path=active_path)
            if after != before:
                raise RuntimeError("active bytes differ from the quarantine source")
            if _object_exists(client, args.bucket, quarantine_path):
                raise RuntimeError(
                    "active copy verified, but the quarantine source still exists"
                )
    except ReleaseLockError as exc:
        print(f"[refused] release lock unavailable: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 — no false success after mutation.
        print(f"[failed] {type(exc).__name__}: {exc}")
        return 1

    print(f"Recovered and byte-verified {blob_hash}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
