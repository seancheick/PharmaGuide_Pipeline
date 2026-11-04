#!/usr/bin/env python3
"""Publish the independently staged safety-alert feed to Supabase.

This is intentionally separate from ``sync_to_supabase.py``: the catalog is a
large, slow release train, while a human-approved regulatory event must be
published without rebuilding it.  The feed is uploaded at a content-addressed
path, then its release row is promoted atomically.  Only after promotion does
the privileged Edge Function send generic FCM nudges.

Nothing is published without a signature from a key pinned for this feed. The
signature is detached and travels in the release row's ``manifest``, so the feed
bytes, ``feed_path`` and ``checksum`` that installed builds read don't change.
Steps: docs/RELEASE_SIGNING_RUNBOOK.md.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from release_manifest import (
    ALERT_FEED_PURPOSE,
    RELEASE_FORMAT,
    ReleaseManifestError,
    canonical_text,
    validate_alert_feed_statement,
    verify_alert_feed_against_pin,
)
from supabase_client import CACHE_CONTROL_IMMUTABLE, STORAGE_BUCKET, get_supabase_client, upload_file


# One operator account, shared by every worktree and staged release directory.
# This is local serialization, not a distributed database compare-and-swap.
_PUBLICATION_LOCK = Path.home() / ".cache" / "pharmaguide" / "safety-alert-publish.lock"

FEED_FILENAME = "safety_alerts.json"
EXTENDED_FEED_FILENAME = "safety_alerts_extended.json"
MANIFEST_FILENAME = "safety_alerts_manifest.json"
STATEMENT_FILENAME = "safety_alerts_release.json"
SIGNATURE_FILENAME = "safety_alerts_release.sig"


def load_staged_release(dist_dir: Path, *, test_project: bool = False) -> Dict[str, Any]:
    """Load and verify a staged feed and its signature before any remote side effect."""
    staged = _load_staged_feed(dist_dir)
    return {**staged, **_load_signature(dist_dir, staged, test_project=test_project)}


def _feeds_named_by(staged: Dict[str, Any]) -> Dict[str, Any]:
    """What a statement must say about this staged release, in its signed shape."""
    extended = staged["manifest"].get("extended_feed")
    return {
        "base_feed": {"path": staged["remote_path"], "checksum": staged["checksum"]},
        "extended_feed": (
            None if extended is None
            else {"path": extended["path"], "checksum": extended["checksum"]}
        ),
    }


def build_statement(dist_dir: Path, *, sequence: int, key_id: str) -> str:
    """The exact text to sign for the staged feed. Needs no key and no remote."""
    statement = {
        "format": RELEASE_FORMAT,
        "purpose": ALERT_FEED_PURPOSE,
        "key_id": key_id,
        "release_sequence": sequence,
        **_feeds_named_by(_load_staged_feed(dist_dir)),
    }
    validate_alert_feed_statement(statement)
    return canonical_text(statement)


def _load_signature(dist_dir: Path, staged: Dict[str, Any], *, test_project: bool) -> Dict[str, Any]:
    statement_path = dist_dir / STATEMENT_FILENAME
    signature_path = dist_dir / SIGNATURE_FILENAME
    if not statement_path.is_file() or not signature_path.is_file():
        raise ReleaseManifestError(
            "this feed must be signed: "
            f"{STATEMENT_FILENAME} and {SIGNATURE_FILENAME} are not both staged. "
            "See docs/RELEASE_SIGNING_RUNBOOK.md"
        )
    text = statement_path.read_bytes().decode("utf-8")
    signature = signature_path.read_text(encoding="utf-8").strip()
    statement = verify_alert_feed_against_pin(text, signature, test_project=test_project)
    named = _feeds_named_by(staged)
    if any(statement[key] != named[key] for key in named):
        raise ReleaseManifestError(
            f"{STATEMENT_FILENAME} does not name this feed; it was signed for another "
            "staged release. Build and sign a new statement"
        )
    return {
        "statement": statement,
        "signed_feed": {"statement": text, "signature": signature},
    }


def _current_sequence(client: Any) -> tuple[int, Any]:
    """The live release's sequence and signed block, read before anything is written.

    A phone refuses a lower sequence than it has verified, so this only saves the
    operator from a release phones would ignore. It reads the row without checking
    the signature: a higher forged value only means picking a higher sequence.
    """
    current = (
        client.table("safety_alert_releases")
        .select("id,manifest")
        .eq("is_current", True)
        .limit(1)
        .execute()
    )
    rows = getattr(current, "data", None) or []
    signed = (rows[0].get("manifest") or {}).get("signed_feed") if rows else None
    if not isinstance(signed, dict):
        return 0, None
    try:
        sequence = json.loads(signed.get("statement", "")).get("release_sequence")
    except (AttributeError, TypeError, ValueError):
        return 0, signed
    return (sequence if type(sequence) is int else 0), signed


def _load_staged_feed(dist_dir: Path) -> Dict[str, Any]:
    """Load and verify the staged feed itself."""
    feed_path = dist_dir / FEED_FILENAME
    manifest_path = dist_dir / MANIFEST_FILENAME
    if not feed_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(
            "safety-alerts feed and manifest must both be staged before sync"
        )

    feed_bytes = feed_path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("checksum")
    actual = f"sha256:{hashlib.sha256(feed_bytes).hexdigest()}"
    if expected != actual:
        raise ValueError(
            f"safety-alerts checksum mismatch: manifest={expected!r}, actual={actual}"
        )
    if not isinstance(manifest.get("feed_version"), str) or not manifest["feed_version"]:
        raise ValueError("safety-alerts manifest has no feed_version")
    if not isinstance(manifest.get("latest_revisions"), dict):
        raise ValueError("safety-alerts manifest has no latest_revisions map")

    try:
        feed = json.loads(feed_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("safety-alerts feed is not valid JSON") from exc
    if not isinstance(feed, dict) or not isinstance(feed.get("alerts"), list):
        raise ValueError("safety-alerts feed has no alerts list")

    # Old builds reject a whole feed on this event, and the dispatcher reads only
    # this file, so it must never reach either of them.
    if any(a.get("event_type") == "interaction_rule" for a in feed["alerts"] if isinstance(a, dict)):
        raise ValueError("an interaction_rule alert is in the feed every build reads")

    digest = actual.removeprefix("sha256:")
    return {
        "feed_path": feed_path,
        "manifest": manifest,
        "checksum": actual,
        "remote_path": f"safety-alerts/sha256/{digest}.json",
        **_load_extended(dist_dir, manifest, feed),
    }


def _load_extended(dist_dir: Path, manifest: Dict[str, Any], feed: Dict[str, Any]) -> Dict[str, Any]:
    extended = manifest.get("extended_feed")
    if extended is None:
        return {}
    path = dist_dir / EXTENDED_FEED_FILENAME
    if not path.is_file():
        raise FileNotFoundError("the manifest names an extended feed that is not staged")
    actual = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    if extended.get("checksum") != actual or feed.get("extended_feed_checksum") != actual:
        raise ValueError(f"extended feed checksum mismatch: actual={actual}")
    digest = actual.removeprefix("sha256:")
    remote = f"safety-alerts/sha256/{digest}.json"
    if extended.get("path") != remote:
        raise ValueError(f"extended feed path mismatch: {extended.get('path')!r}")
    return {"extended_feed_path": path, "extended_remote_path": remote}


def sync(dist_dir: Path, *, dry_run: bool = False, test_project: bool = False) -> Dict[str, Any]:
    staged = load_staged_release(dist_dir, test_project=test_project)
    if dry_run:
        return {"status": "dry_run", **staged}

    _PUBLICATION_LOCK.parent.mkdir(parents=True, exist_ok=True)
    # Keep the descriptor open through sequence validation, remote writes,
    # promotion and dispatch. Never unlink the lock: that permits a new inode
    # to be locked while another publisher still holds the old one.
    with _PUBLICATION_LOCK.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("another safety-alert publication is running") from error
        return _publish_staged(staged)


def _publish_staged(staged: Dict[str, Any]) -> Dict[str, Any]:
    # Installed builds never read this key, and the dispatcher never reads `manifest`.
    manifest = {**staged["manifest"], "signed_feed": staged["signed_feed"]}
    # Missing local configuration must fail before upload or promotion. Dispatch
    # can still fail remotely after promotion, but that is a retryable delivery
    # failure, not permission to publish without a configured dispatcher.
    _dispatch_configuration()
    client = get_supabase_client()
    current_sequence, current_signed = _current_sequence(client)
    sequence = staged["statement"]["release_sequence"]
    if sequence <= current_sequence and current_signed != staged["signed_feed"]:
        raise ReleaseManifestError(
            f"release_sequence {sequence} must be higher than the current release's "
            f"{current_sequence}. Build and sign a new statement"
        )
    # Before anything can name it: a build must never be told to fetch a missing file.
    if "extended_feed_path" in staged:
        upload_file(
            client,
            STORAGE_BUCKET,
            staged["extended_remote_path"],
            staged["extended_feed_path"],
            content_type="application/json",
            upsert=True,
            cache_control=CACHE_CONTROL_IMMUTABLE,
        )
    upload_file(
        client,
        STORAGE_BUCKET,
        staged["remote_path"],
        staged["feed_path"],
        content_type="application/json",
        # A prior run may have uploaded the immutable bytes but failed before
        # database promotion. Re-uploading the same hash-addressed object is
        # safe and makes the release retryable.
        upsert=True,
        cache_control=CACHE_CONTROL_IMMUTABLE,
    )

    existing = (
        client.table("safety_alert_releases")
        .select("id,manifest")
        .eq("checksum", staged["checksum"])
        .limit(1)
        .execute()
    )
    rows = getattr(existing, "data", None) or []
    if rows:
        release_id = rows[0]["id"]
        # A return to earlier bytes finds the earlier row, whose lower sequence
        # phones would refuse. It must carry the signature just verified.
        if (rows[0].get("manifest") or {}).get("signed_feed") != staged["signed_feed"]:
            client.table("safety_alert_releases").update({"manifest": manifest}).eq(
                "id", release_id
            ).execute()
    else:
        inserted = (
            client.table("safety_alert_releases")
            .insert(
                {
                    "feed_version": manifest["feed_version"],
                    "feed_path": staged["remote_path"],
                    "checksum": staged["checksum"],
                    "manifest": manifest,
                }
            )
            .execute()
        )
        inserted_rows = getattr(inserted, "data", None) or []
        if len(inserted_rows) != 1 or not inserted_rows[0].get("id"):
            raise RuntimeError("safety-alert release insert returned no id")
        release_id = inserted_rows[0]["id"]

    client.rpc("promote_safety_alert_release", {"p_release_id": release_id}).execute()
    _dispatch_release(release_id)
    return {"status": "published", "release_id": release_id, **staged}


def _dispatch_configuration() -> tuple[str, str]:
    """Validate local dispatch prerequisites without contacting the server."""
    import env_loader  # noqa: F401

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    secret = os.environ.get("SAFETY_ALERT_DISPATCH_SECRET", "")
    if not url or not secret:
        raise RuntimeError(
            "SUPABASE_URL and SAFETY_ALERT_DISPATCH_SECRET are required to dispatch safety alerts"
        )
    return url, secret


def _dispatch_release(release_id: str) -> None:
    """Invoke the server-only dispatcher after atomic release promotion."""
    import requests

    url, secret = _dispatch_configuration()
    response = requests.post(
        f"{url}/functions/v1/dispatch-safety-alert-release",
        headers={"x-safety-alert-dispatch-secret": secret},
        json={"release_id": release_id},
        timeout=30,
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(
            "safety-alert dispatch failed after release promotion: "
            f"HTTP {response.status_code}: {response.text[:300]}"
        )
    # HTTP 200 alone is not delivery: the dispatcher reports per-device results
    # in its body, and undelivered rows stay queued for a retry invocation.
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "safety-alert dispatch returned an unreadable body; "
            "deliveries are unverified"
        ) from exc
    if body.get("ok") is not True:
        raise RuntimeError(
            "safety-alert dispatch left undelivered pushes queued: "
            f"sent={body.get('sent')} failed={body.get('failed')} "
            f"removed={body.get('removed')} — re-run dispatch for this release"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir", type=Path, default=SCRIPTS / "dist", help="staged artifact directory"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--test-project", action="store_true",
        help="publish to a listed test host, signed with a key under test_keys",
    )
    parser.add_argument(
        "--build-statement", action="store_true",
        help="write the text to sign for the staged feed, then stop; needs no key or remote",
    )
    parser.add_argument("--sequence", type=int, help="with --build-statement")
    parser.add_argument("--key-id", help="with --build-statement")
    args = parser.parse_args()
    try:
        if args.build_statement:
            if args.sequence is None or not args.key_id:
                parser.error("--build-statement needs --sequence and --key-id")
            path = args.dist_dir / STATEMENT_FILENAME
            path.write_text(
                build_statement(args.dist_dir, sequence=args.sequence, key_id=args.key_id),
                encoding="utf-8",
            )
            print(f"[safety-alerts] wrote {path}; sign it on the custody machine")
            return 0
        result = sync(args.dist_dir, dry_run=args.dry_run, test_project=args.test_project)
    except ReleaseManifestError as error:
        print(f"[safety-alerts] refused: {error}", file=sys.stderr)
        return 1
    print(f"[safety-alerts] {result['status']}: {result['checksum']}")
    if result["status"] == "published":
        print(f"[safety-alerts] release_id={result['release_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
