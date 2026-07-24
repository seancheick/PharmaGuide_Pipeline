"""Versioned medication-depletions runtime artifact generator (B1.2).

Produces the app-bound `medication_depletions` artifact from the canonical
source. Responsibilities:
  * Validate every referenced id (drug subject + nutrient canonical id) and
    REJECT a malformed asset — the pipeline is the PRIMARY identity gate; the
    app only defensively declines activation.
  * Inject citation-review defaults so every emitted entry carries a review
    status (`unverified` until the content audit authors otherwise). The status
    gates publication, not display copy — "unverified" is never shown to users.
  * Stamp versioned metadata: `schema_version`, `content_version` (release
    stamp), `content_hash` (sha256 over the clinical entries, NOT the release
    stamp), and `minimum_runtime_contract` (bumped only on an incompatible
    shape change).

Pure `build_artifact(source, content_version=...)` core + a thin CLI that reads
the canonical file and writes the artifact (wired into the build/sync later).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any, Dict, List

# Schema version of the emitted artifact. Bumped from the source's 5.3.0 to
# signal the added citation-review fields (additive, back-compatible).
ARTIFACT_SCHEMA_VERSION = "5.4.0"

# Contract version the app checks before activating the artifact. Bump ONLY on
# an incompatible shape change (a field the app must understand to render
# safely). Additive optional fields do NOT bump this.
MINIMUM_RUNTIME_CONTRACT = 1

CITATION_REVIEW_STATES = {"unverified", "verified", "needs_revision", "rejected"}
DEFAULT_REVIEW_STATUS = "unverified"

TOP_LEVEL_KEY = "depletions"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(f"medication_depletions artifact: {msg}")


def _validate_and_normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one entry's identity + review status; return a normalized copy
    with citation-review defaults injected. Raises ValueError on a malformed
    entry (rejecting the whole asset is the caller's job)."""
    _require(isinstance(entry, dict), "entry is not an object")

    entry_id = str(entry.get("id") or "").strip()
    _require(bool(entry_id), "entry is missing a stable `id`")

    drug_ref = entry.get("drug_ref") or {}
    drug_id = str(drug_ref.get("id") or "").strip()
    drug_name = str(drug_ref.get("display_name") or "").strip()
    _require(
        bool(drug_id or drug_name),
        f"{entry_id}: drug_ref has neither `id` nor `display_name`",
    )

    nutrient = entry.get("depleted_nutrient") or {}
    canonical_id = str(nutrient.get("canonical_id") or "").strip()
    _require(
        bool(canonical_id), f"{entry_id}: depleted_nutrient.canonical_id is missing"
    )

    status = entry.get("citation_review_status", DEFAULT_REVIEW_STATUS)
    if status is None:
        status = DEFAULT_REVIEW_STATUS
    status = str(status).strip().lower()
    _require(
        status in CITATION_REVIEW_STATES,
        f"{entry_id}: citation_review_status {status!r} not in "
        f"{sorted(CITATION_REVIEW_STATES)}",
    )

    out = dict(entry)
    out["citation_review_status"] = status
    out["reviewed_at"] = entry.get("reviewed_at")  # null unless authored
    out["reviewer"] = entry.get("reviewer")  # null unless authored
    return out


def _content_hash(entries: List[Dict[str, Any]]) -> str:
    """sha256 over the clinical entries in a canonical serialization. Covers the
    content (incl. review status), NOT the release version stamp, so the app can
    distinguish a content change from a new release."""
    canonical = json.dumps(
        entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_artifact(source: Dict[str, Any], *, content_version: str) -> Dict[str, Any]:
    """Build the versioned runtime artifact from the canonical source dict."""
    entries = source.get(TOP_LEVEL_KEY)
    _require(isinstance(entries, list), f"source missing `{TOP_LEVEL_KEY}` list")

    seen_ids: set[str] = set()
    out_entries: List[Dict[str, Any]] = []
    for entry in entries:
        normalized = _validate_and_normalize_entry(entry)
        eid = str(normalized["id"]).strip()
        _require(eid not in seen_ids, f"duplicate entry id {eid!r}")
        seen_ids.add(eid)
        out_entries.append(normalized)

    metadata = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "content_version": content_version,
        "content_hash": f"sha256:{_content_hash(out_entries)}",
        "minimum_runtime_contract": MINIMUM_RUNTIME_CONTRACT,
        "total_entries": len(out_entries),
        "generated_by": "build_medication_depletions_artifact",
    }
    return {"_metadata": metadata, TOP_LEVEL_KEY: out_entries}


def _default_content_version() -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return f"{now.year:04d}.{now.month:02d}.{now.day:02d}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the versioned medication-depletions runtime artifact."
    )
    parser.add_argument("source", help="canonical medication_depletions.json path")
    parser.add_argument("output", help="path to write the versioned artifact")
    parser.add_argument(
        "--content-version",
        default=None,
        help="release stamp (default: today's UTC date, YYYY.MM.DD)",
    )
    args = parser.parse_args(argv)

    with open(args.source, encoding="utf-8") as f:
        source = json.load(f)
    content_version = args.content_version or _default_content_version()
    artifact = build_artifact(source, content_version=content_version)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(
        f"wrote {artifact['_metadata']['total_entries']} entries -> {args.output} "
        f"({artifact['_metadata']['content_hash']}, v{content_version})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
