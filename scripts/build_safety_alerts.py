#!/usr/bin/env python3
"""Publish the safety-alert fast lane: resolve scope, then stage feed + manifest.

Runs independently of the catalog build. That is the whole point — a recall must
not wait on a 27-minute enrich/score cycle plus human release gates, and the
catalog must not be rebuilt to say "stop taking this".

Modelled on `release_interaction_artifact.py`, which already ships a small,
separately-versioned artifact next to the catalog. Same contract, deliberately:

  * the manifest carries the checksum; the feed never embeds its own hash
    (a file cannot contain its own digest without invalidating it)
  * the manifest is the sole source of truth for the checksum

Resolution
----------
`resolved_dsld_ids` is the SIGNED, publication-time applicability set — not
merely push targeting. A device may hold a catalog snapshot older than the
alert, in which case its local identities cannot resolve the newly banned
substance at all and canonical matching would silently miss it. Resolving here,
against a pinned snapshot, is what lets a ban work BEFORE the catalog rebuild.

The index is built from each product's `display_ingredients[].canonical_id` in
the shipped detail blobs. That list is deliberate:

  * it is the COMPLETE ingredient list — actives, inactives, and demoted rows
    alike. A banned substance must not escape resolution because scoring demoted
    it (Bioperine at 5 mg is demoted to an absorption aid yet is still
    physically in the bottle).
  * it is the artifact the device itself holds, so publication-time resolution
    and on-device confirmation read the same identities.

Matching is exact canonical-id equality. Never name similarity: a substring hit
is not proof of identity, and an alert that condemns the wrong product is worse
than one that arrives a day later.

Usage
-----
    python3 scripts/build_safety_alerts.py --check      # validate only
    python3 scripts/build_safety_alerts.py --resolve    # write resolution into records
    python3 scripts/build_safety_alerts.py --stage      # emit dist/ feed + manifest
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from safety_alerts import (  # noqa: E402
    SCHEMA_VERSION,
    is_active,
    latest_revisions,
    validate_feed,
)

ALERTS_DIR = SCRIPTS / "data" / "safety_alerts"
DIST_DIR = SCRIPTS / "dist"
BLOBS_DIR = DIST_DIR / "detail_blobs"
CATALOG_MANIFEST = DIST_DIR / "export_manifest.json"

FEED_FILENAME = "safety_alerts.json"
MANIFEST_FILENAME = "safety_alerts_manifest.json"


def load_alert_records(alerts_dir: Path = ALERTS_DIR) -> List[Dict[str, Any]]:
    """Every `SA_*.json` in the directory. `_`-prefixed files are templates."""
    records = []
    for path in sorted(alerts_dir.glob("SA_*.json")):
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        record["_source_path"] = str(path)
        records.append(record)
    return records


def catalog_snapshot_version(manifest_path: Path = CATALOG_MANIFEST) -> Optional[str]:
    """The db_version the resolution is pinned to."""
    if not manifest_path.exists():
        return None
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return json.load(handle).get("db_version")


def build_ingredient_index(blobs_dir: Path = BLOBS_DIR) -> Dict[str, Set[str]]:
    """canonical_id -> {dsld_id}, from the shipped blobs' complete ingredient list.

    Reads `display_ingredients` rather than `ingredients`, because the latter
    excludes demoted rows. See the module docstring.
    """
    index: Dict[str, Set[str]] = defaultdict(set)
    for path in blobs_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                blob = json.load(handle)
        except (OSError, ValueError):
            continue
        dsld_id = str(blob.get("dsld_id") or path.stem)
        for row in blob.get("display_ingredients") or []:
            if not isinstance(row, dict):
                continue
            canonical_id = row.get("canonical_id")
            if isinstance(canonical_id, str) and canonical_id.strip():
                index[canonical_id.strip()].add(dsld_id)
    return index


def resolve_scope(
    record: Dict[str, Any],
    index: Dict[str, Set[str]],
    known_dsld_ids: Set[str],
) -> Tuple[List[str], List[str]]:
    """Return (resolved_dsld_ids, warnings) for one alert."""
    warnings: List[str] = []
    scope = record.get("scope") or {}
    resolved: Set[str] = set()

    for canonical_id in scope.get("ingredient_canonical_ids") or []:
        hits = index.get(canonical_id)
        if not hits:
            # Not an error: the substance may simply not appear in this catalog
            # snapshot. It is worth a curator's attention though, because the
            # usual cause is an id typo or a vocabulary mismatch.
            warnings.append(
                f"ingredient canonical_id {canonical_id!r} matches no product in this "
                f"catalog snapshot — confirm the id against the catalog's vocabulary"
            )
            continue
        resolved |= hits

    for dsld_id in scope.get("dsld_ids") or []:
        if dsld_id not in known_dsld_ids:
            warnings.append(f"dsld_id {dsld_id!r} is not in this catalog snapshot")
            continue
        resolved.add(dsld_id)

    return sorted(resolved), warnings


def resolve_all(records: List[Dict[str, Any]], *, write: bool) -> Dict[str, Any]:
    """Resolve every record's scope against the current catalog snapshot."""
    snapshot = catalog_snapshot_version()
    if not snapshot:
        return {"ok": False, "errors": [f"no catalog manifest at {CATALOG_MANIFEST}"], "warnings": []}
    if not BLOBS_DIR.exists():
        return {"ok": False, "errors": [f"no detail blobs at {BLOBS_DIR}"], "warnings": []}

    index = build_ingredient_index()
    known = {str(p.stem) for p in BLOBS_DIR.glob("*.json")}
    warnings: List[str] = []

    for record in records:
        resolved, record_warnings = resolve_scope(record, index, known)
        warnings.extend(f"{record.get('alert_id')}: {w}" for w in record_warnings)
        record["resolved_dsld_ids"] = resolved
        record["catalog_snapshot_version"] = snapshot

        if write:
            path = record.get("_source_path")
            if not path:
                continue
            payload = {k: v for k, v in record.items() if not k.startswith("_")}
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")

    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "snapshot": snapshot,
        "indexed_ingredients": len(index),
    }


def build_feed(records: List[Dict[str, Any]], today: str) -> Dict[str, Any]:
    """The shipped feed: latest revision per alert_id, active records only.

    Retracted and expired alerts are dropped from the feed rather than shipped
    as tombstones — a client that no longer sees an alert clears ONLY that
    alert's own signal. It must never clear a catalog BLOCKED verdict; the two
    lanes do not clear each other.
    """
    latest = latest_revisions(records)
    published = [
        {k: v for k, v in record.items() if not k.startswith("_")}
        for record in latest.values()
        if is_active(record, today)
    ]
    published.sort(key=lambda r: (r.get("published_at") or "", r.get("alert_id")))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": today,
        "alert_count": len(published),
        "alerts": published,
    }


def stage(records: List[Dict[str, Any]], today: str, dist_dir: Path = DIST_DIR) -> Dict[str, Any]:
    """Write feed + manifest into dist/. Checksum lives in the manifest only."""
    feed = build_feed(records, today)
    payload = json.dumps(feed, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    dist_dir.mkdir(parents=True, exist_ok=True)
    feed_path = dist_dir / FEED_FILENAME
    manifest_path = dist_dir / MANIFEST_FILENAME

    # Atomic: write beside, then replace. A partially written feed must never be
    # readable, because a client that reads one would fail its checksum and drop
    # back to last-known-good for no reason.
    tmp = feed_path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(feed_path)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "feed_version": today,
        "checksum": f"sha256:{digest}",
        "alert_count": feed["alert_count"],
        "catalog_snapshot_version": catalog_snapshot_version(),
        # Clients ignore a revision they have already applied, and never apply a
        # lower one. Shipping the map lets them decide without parsing the feed.
        "latest_revisions": {a["alert_id"]: a["revision"] for a in feed["alerts"]},
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"feed": str(feed_path), "manifest": str(manifest_path), **manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate only, write nothing")
    parser.add_argument("--resolve", action="store_true", help="resolve scope into the record files")
    parser.add_argument("--stage", action="store_true", help="emit dist/ feed + manifest")
    parser.add_argument("--today", help="YYYY-MM-DD; defaults to the catalog snapshot's date")
    args = parser.parse_args()

    if not (args.check or args.resolve or args.stage):
        parser.error("pass one of --check, --resolve, --stage")

    records = load_alert_records()
    print(f"[safety-alerts] {len(records)} record(s) in {ALERTS_DIR}")

    if args.resolve or args.stage:
        outcome = resolve_all(records, write=args.resolve)
        if not outcome["ok"]:
            for message in outcome["errors"]:
                print(f"[safety-alerts] RESOLUTION FAILED: {message}", file=sys.stderr)
            return 1
        print(
            f"[safety-alerts] resolved against catalog {outcome['snapshot']} "
            f"({outcome['indexed_ingredients']} distinct canonical ids indexed)"
        )
        for message in outcome["warnings"]:
            print(f"[safety-alerts] warning: {message}")

    validation = validate_feed([{k: v for k, v in r.items() if not k.startswith("_")} for r in records])
    for message in validation["warnings"]:
        print(f"[safety-alerts] warning: {message}")
    if not validation["ok"]:
        for message in validation["errors"]:
            print(f"[safety-alerts] INVALID: {message}", file=sys.stderr)
        return 1
    print("[safety-alerts] validation passed")

    if args.stage:
        today = args.today
        if not today:
            snapshot = catalog_snapshot_version() or ""
            # db_version is YYYY.MM.DD.HHMMSS
            parts = snapshot.split(".")
            today = "-".join(parts[:3]) if len(parts) >= 3 else ""
        if not today:
            print("[safety-alerts] STAGING FAILED: pass --today YYYY-MM-DD", file=sys.stderr)
            return 1
        staged = stage(records, today)
        print(f"[safety-alerts] staged -> {staged['feed']}")
        print(f"[safety-alerts]   alerts   = {staged['alert_count']}")
        print(f"[safety-alerts]   checksum = {staged['checksum']}")
        print(f"[safety-alerts]   catalog  = {staged['catalog_snapshot_version']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
