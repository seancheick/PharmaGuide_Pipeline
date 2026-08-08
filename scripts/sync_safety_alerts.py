#!/usr/bin/env python3
"""Publish the independently staged safety-alert feed to Supabase.

This is intentionally separate from ``sync_to_supabase.py``: the catalog is a
large, slow release train, while a human-approved regulatory event must be
published without rebuilding it.  The feed is uploaded at a content-addressed
path, then its release row is promoted atomically.  Only after promotion does
the privileged Edge Function send generic FCM nudges.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from supabase_client import CACHE_CONTROL_IMMUTABLE, get_supabase_client, upload_file


BUCKET = "pharmaguide"
FEED_FILENAME = "safety_alerts.json"
MANIFEST_FILENAME = "safety_alerts_manifest.json"


def load_staged_release(dist_dir: Path) -> Dict[str, Any]:
    """Load and verify a staged feed before any remote side effect."""
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

    digest = actual.removeprefix("sha256:")
    return {
        "feed_path": feed_path,
        "manifest": manifest,
        "checksum": actual,
        "remote_path": f"safety-alerts/sha256/{digest}.json",
    }


def sync(dist_dir: Path, *, dry_run: bool = False) -> Dict[str, Any]:
    staged = load_staged_release(dist_dir)
    manifest = staged["manifest"]
    if dry_run:
        return {"status": "dry_run", **staged}

    client = get_supabase_client()
    upload_file(
        client,
        BUCKET,
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
        .select("id")
        .eq("checksum", staged["checksum"])
        .limit(1)
        .execute()
    )
    rows = getattr(existing, "data", None) or []
    if rows:
        release_id = rows[0]["id"]
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


def _dispatch_release(release_id: str) -> None:
    """Invoke the server-only dispatcher after atomic release promotion."""
    import requests
    import env_loader  # noqa: F401

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    secret = os.environ.get("SAFETY_ALERT_DISPATCH_SECRET", "")
    if not url or not secret:
        raise RuntimeError(
            "SUPABASE_URL and SAFETY_ALERT_DISPATCH_SECRET are required to dispatch safety alerts"
        )
    response = requests.post(
        f"{url}/functions/v1/dispatch-safety-alert-release",
        headers={"x-safety-alert-dispatch-secret": secret},
        json={"release_id": release_id},
        timeout=30,
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(
            "safety-alert dispatch failed after release promotion: "
            f"HTTP {response.status_code}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir", type=Path, default=SCRIPTS / "dist", help="staged artifact directory"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = sync(args.dist_dir, dry_run=args.dry_run)
    print(f"[safety-alerts] {result['status']}: {result['checksum']}")
    if result["status"] == "published":
        print(f"[safety-alerts] release_id={result['release_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
