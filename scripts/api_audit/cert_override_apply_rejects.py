#!/usr/bin/env python3
"""P1.7.2 — apply cluster-report reject suggestions to overrides.

Reads the P1.7.1 cluster triage report (JSON) and promotes every
`suggested_action: reject` cluster into per-product override entries
in `scripts/data/curated_overrides/cert_verification_overrides.json`.

Scoring impact is zero — both `needs_review` (the previous resolver
verdict for these matches) and `claimed_only` (the post-reject verdict)
score 0 in v4 B4a. This slice is audit hygiene that locks the
"not verified" answer behind explicit reviewer evidence so the
resolver doesn't re-derive the same fuzzy match next pipeline rerun.

Each override entry carries forensic metadata:
  - dsld_id          (the product being rejected)
  - record_id        (the registry row that was wrongly matched)
  - matched_brand    (the registry row's brand — often the false-positive evidence)
  - matched_product  (the registry row's product name)
  - reason           (the triage-hint reason codes: dose_mismatch / brand_mismatch / ...)
  - review_source    (which audit run produced this — for traceability)
  - reviewed_at      (date stamp)

The merge is idempotent: re-running the script with the same input
won't duplicate entries. Existing override entries (the 32 manually
reviewed ones shipped to date) are preserved verbatim.

Usage:
    python3 scripts/api_audit/cert_override_apply_rejects.py \\
        [--cluster-report scripts/api_audit/reports/cert_needs_review_clusters.json] \\
        [--overrides-path scripts/data/curated_overrides/cert_verification_overrides.json] \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


DEFAULT_CLUSTER_REPORT = (
    SCRIPTS_ROOT / "api_audit" / "reports" / "cert_needs_review_clusters.json"
)
DEFAULT_OVERRIDES_PATH = (
    SCRIPTS_ROOT / "data" / "curated_overrides" / "cert_verification_overrides.json"
)


# --- Generators ---------------------------------------------------------


def generate_overrides_for_cluster(
    cluster: Dict[str, Any],
    *,
    review_source: str,
) -> List[Dict[str, Any]]:
    """Convert a single `suggested_action: reject` cluster into N override
    entries (one per member). Non-reject clusters return []."""
    if cluster.get("suggested_action") != "reject":
        return []

    today = date.today().isoformat()
    program = cluster.get("program", "")
    record_id = cluster.get("record_id", "")

    entries: List[Dict[str, Any]] = []
    for member in cluster.get("members") or []:
        if not isinstance(member, dict):
            continue
        triage = member.get("triage_hint") or {}
        member_reasons = triage.get("reasons") or []
        reason_text = ", ".join(member_reasons) or "auto_classifier_reject"
        entry = {
            "brand": member.get("brand_name", ""),
            "product": member.get("product_name", ""),
            "program": program,
            "status": "rejected",
            "scope": "claimed_only",
            "reason": (
                f"P1.7.2 auto-reject — {reason_text}. "
                f"Product matched the registry row "
                f"`{member.get('matched_product', '?')}` "
                f"owned by `{member.get('matched_brand', '?')}` "
                f"but failed conservative same-product checks."
            ),
            "reviewed_at": today,
            "review_source": review_source,
            "dsld_id": str(member.get("dsld_id", "")),
            "record_id": record_id,
            "matched_brand": member.get("matched_brand", ""),
            "matched_product": member.get("matched_product", ""),
            "triage_reasons": member_reasons,
        }
        entries.append(entry)
    return entries


# --- File I/O -----------------------------------------------------------


def merge_into_overrides_file(
    overrides_path: Path,
    new_entries: List[Dict[str, Any]],
) -> int:
    """Append new override entries to the existing overrides file,
    preserving existing entries + _metadata. Returns the number of
    entries actually added (idempotent — duplicates suppressed)."""
    if not overrides_path.exists():
        payload: Dict[str, Any] = {
            "_metadata": {
                "schema_version": "6.0.0",
                "description": "Manual overrides for cert verification scope.",
                "purpose": "cert_verification_manual_override",
                "last_updated": "",
                "total_overrides": 0,
            },
            "overrides": [],
        }
    else:
        payload = json.loads(overrides_path.read_text())

    existing = payload.setdefault("overrides", [])
    # Dedupe key: (program, record_id, dsld_id). Same triple = same logical
    # decision; the merge skips re-applying it.
    existing_keys = {
        (o.get("program", ""), o.get("record_id", ""), str(o.get("dsld_id", "")))
        for o in existing
        if isinstance(o, dict)
    }

    added = 0
    for entry in new_entries:
        key = (
            entry.get("program", ""),
            entry.get("record_id", ""),
            str(entry.get("dsld_id", "")),
        )
        if key in existing_keys:
            continue
        existing.append(entry)
        existing_keys.add(key)
        added += 1

    if added:
        payload.setdefault("_metadata", {})
        payload["_metadata"]["total_overrides"] = len(existing)
        payload["_metadata"]["last_updated"] = date.today().isoformat()

    overrides_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return added


# --- CLI ----------------------------------------------------------------


def _parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--cluster-report", type=Path, default=DEFAULT_CLUSTER_REPORT,
        help="Path to the P1.7.1 cluster JSON report.",
    )
    parser.add_argument(
        "--overrides-path", type=Path, default=DEFAULT_OVERRIDES_PATH,
        help="Target curated_overrides JSON file.",
    )
    parser.add_argument(
        "--review-source", type=str,
        default=f"P1.7.2_auto_reject_{date.today().isoformat()}",
        help="`review_source` value written to each new override entry.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would change without modifying the overrides file.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.cluster_report.exists():
        print(f"Cluster report not found: {args.cluster_report}", file=sys.stderr)
        return 2
    report = json.loads(args.cluster_report.read_text())
    clusters = report.get("clusters") or []

    new_entries: List[Dict[str, Any]] = []
    reject_cluster_count = 0
    for cluster in clusters:
        if cluster.get("suggested_action") == "reject":
            reject_cluster_count += 1
        entries = generate_overrides_for_cluster(cluster, review_source=args.review_source)
        new_entries.extend(entries)

    print(f"Found {reject_cluster_count} reject clusters → {len(new_entries)} candidate override entries")

    if args.dry_run:
        # Print summary of would-add entries
        by_program: Dict[str, int] = {}
        by_reason: Dict[str, int] = {}
        for e in new_entries:
            by_program[e.get("program", "?")] = by_program.get(e.get("program", "?"), 0) + 1
            for r in e.get("triage_reasons", []):
                by_reason[r] = by_reason.get(r, 0) + 1
        print(f"  By program: {by_program}")
        print(f"  By reason:  {by_reason}")
        print(f"  (dry-run — overrides file NOT modified)")
        return 0

    added = merge_into_overrides_file(args.overrides_path, new_entries)
    print(f"  Wrote {added} new override entries to {args.overrides_path}")
    print(f"  (skipped {len(new_entries) - added} duplicates already in file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
