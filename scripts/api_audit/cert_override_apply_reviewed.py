#!/usr/bin/env python3
"""P1.7.3 — apply manually reviewed cert cluster decisions.

This is intentionally NOT an auto-classifier. It reads the P1.7.1
`cert_needs_review_clusters.json` report, selects exactly one cluster by
program + record_id, and converts an explicit reviewer decision into
curated override entries.

Use this for score-moving decisions such as confirmed product-line variants:

    python3 scripts/api_audit/cert_override_apply_reviewed.py \
        --program "Informed Choice" \
        --record-id INFORMED_CHO_65E7FB3D998C \
        --action verify_product_line \
        --reviewer Sean \
        --review-note "Reviewed cluster table; members are AMP Wheybolic flavor variants."

Mixed clusters can be limited to specific reviewed members with repeated
`--member-dsld-id` flags. Existing overrides are preserved and duplicate
entries are suppressed by the shared override merge helper.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

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

VALID_ACTIONS = {"verify_product_line", "reject"}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def find_cluster(
    clusters: Iterable[Dict[str, Any]],
    *,
    program: str,
    record_id: str,
) -> Dict[str, Any]:
    """Find one cluster by stable program + record_id identifiers."""
    program_norm = _norm(program)
    record_norm = str(record_id or "").strip()
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        if _norm(cluster.get("program")) == program_norm and str(cluster.get("record_id") or "").strip() == record_norm:
            return cluster
    raise ValueError(f"cluster not found for program={program!r}, record_id={record_id!r}")


def _selected_members(
    cluster: Dict[str, Any],
    member_dsld_ids: Set[str] | None,
) -> List[Dict[str, Any]]:
    members = [m for m in cluster.get("members") or [] if isinstance(m, dict)]
    if not member_dsld_ids:
        return members
    wanted = {str(v) for v in member_dsld_ids}
    selected = [m for m in members if str(m.get("dsld_id") or "") in wanted]
    found = {str(m.get("dsld_id") or "") for m in selected}
    missing = sorted(wanted - found)
    if missing:
        raise ValueError(f"member dsld_id not found in cluster: {', '.join(missing)}")
    return selected


def _validate_review(action: str, review_note: str, reviewer: str) -> None:
    if action not in VALID_ACTIONS:
        raise ValueError(f"unsupported action: {action!r}")
    if not str(review_note or "").strip():
        raise ValueError("review note is required")
    if not str(reviewer or "").strip():
        raise ValueError("reviewer is required")


def generate_reviewed_overrides(
    cluster: Dict[str, Any],
    *,
    action: str,
    review_note: str,
    reviewer: str,
    review_source: str,
    member_dsld_ids: Set[str] | None = None,
    override_record_id: str | None = None,
    override_matched_brand: str | None = None,
    override_matched_product: str | None = None,
) -> List[Dict[str, Any]]:
    """Convert one manually reviewed cluster decision into override entries."""
    _validate_review(action, review_note, reviewer)
    members = _selected_members(cluster, member_dsld_ids)
    if not members:
        raise ValueError("selected cluster has no members")

    today = date.today().isoformat()
    status = "verified" if action == "verify_product_line" else "rejected"
    scope = "product_line" if action == "verify_product_line" else "claimed_only"
    program = str(cluster.get("program") or "")
    cluster_record_id = str(cluster.get("record_id") or "")
    record_id = str(override_record_id or cluster_record_id)
    matched_brand = str(override_matched_brand or cluster.get("matched_brand") or "")
    matched_product = str(override_matched_product or cluster.get("matched_product") or "")

    entries: List[Dict[str, Any]] = []
    for member in members:
        triage_reasons = list((member.get("triage_hint") or {}).get("reasons", []))
        if override_record_id:
            triage_reasons.append(f"alternate_record_id={record_id}")
        entry = {
            "brand": member.get("brand_name", ""),
            "product": member.get("product_name", ""),
            "program": program,
            "status": status,
            "scope": scope,
            "reason": f"P1.7.3 manual {action} — {review_note.strip()}",
            "reviewed_at": today,
            "review_source": review_source,
            "reviewer": reviewer.strip(),
            "dsld_id": str(member.get("dsld_id", "")),
            "record_id": record_id,
            "matched_brand": member.get("matched_brand") or matched_brand,
            "matched_product": member.get("matched_product") or matched_product,
            "triage_reasons": triage_reasons,
        }
        if override_matched_brand:
            entry["matched_brand"] = matched_brand
        if override_matched_product:
            entry["matched_product"] = matched_product
        entries.append(entry)
    return entries


def merge_reviewed_into_overrides_file(
    overrides_path: Path,
    entries: List[Dict[str, Any]],
    *,
    replace_program_dsld_conflicts: bool = False,
) -> tuple[int, int, int]:
    """Upsert manually reviewed decisions into the curated overrides file.

    Reviewed decisions are allowed to promote a previous pending_review row for
    the same (program, record_id, dsld_id). Auto-reject imports intentionally
    skip duplicates, but human-reviewed decisions are authoritative.
    """
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
    removed_conflicts = 0
    if replace_program_dsld_conflicts and entries:
        incoming_pairs = {
            (entry.get("program", ""), str(entry.get("dsld_id", "")), entry.get("record_id", ""))
            for entry in entries
            if entry.get("program") and str(entry.get("dsld_id", ""))
        }
        incoming_program_dslds = {
            (program, dsld_id)
            for program, dsld_id, _record_id in incoming_pairs
        }
        filtered_existing = []
        for override in existing:
            if not isinstance(override, dict):
                filtered_existing.append(override)
                continue
            pair = (override.get("program", ""), str(override.get("dsld_id", "")))
            same_record = (
                override.get("program", ""),
                str(override.get("dsld_id", "")),
                override.get("record_id", ""),
            ) in incoming_pairs
            if pair in incoming_program_dslds and not same_record:
                removed_conflicts += 1
                continue
            filtered_existing.append(override)
        existing[:] = filtered_existing

    index: dict[tuple[str, str, str], int] = {}
    for idx, override in enumerate(existing):
        if not isinstance(override, dict):
            continue
        key = (
            override.get("program", ""),
            override.get("record_id", ""),
            str(override.get("dsld_id", "")),
        )
        index[key] = idx

    added = 0
    replaced = 0
    for entry in entries:
        key = (
            entry.get("program", ""),
            entry.get("record_id", ""),
            str(entry.get("dsld_id", "")),
        )
        existing_idx = index.get(key)
        if existing_idx is None:
            existing.append(entry)
            index[key] = len(existing) - 1
            added += 1
            continue
        if existing[existing_idx] != entry:
            existing[existing_idx] = entry
            replaced += 1

    if added or replaced or removed_conflicts:
        payload.setdefault("_metadata", {})
        payload["_metadata"]["total_overrides"] = len(existing)
        payload["_metadata"]["last_updated"] = date.today().isoformat()

    overrides_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    )
    return added, replaced, removed_conflicts


def _parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cluster-report", type=Path, default=DEFAULT_CLUSTER_REPORT)
    parser.add_argument("--overrides-path", type=Path, default=DEFAULT_OVERRIDES_PATH)
    parser.add_argument("--program", required=True)
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--action", choices=sorted(VALID_ACTIONS), required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--review-note", required=True)
    parser.add_argument(
        "--review-source",
        default=f"P1.7.3_manual_review_{date.today().isoformat()}",
    )
    parser.add_argument(
        "--member-dsld-id",
        action="append",
        default=[],
        help="Limit the action to one reviewed DSLD ID. May be repeated.",
    )
    parser.add_argument(
        "--override-record-id",
        help=(
            "Use an alternate registry record_id for selected members. "
            "Requires --replace-program-dsld-conflicts."
        ),
    )
    parser.add_argument(
        "--override-matched-brand",
        help="Override matched_brand in emitted entries when using an alternate registry row.",
    )
    parser.add_argument(
        "--override-matched-product",
        help="Override matched_product in emitted entries when using an alternate registry row.",
    )
    parser.add_argument(
        "--replace-program-dsld-conflicts",
        action="store_true",
        help=(
            "Remove existing overrides for the same program + dsld_id but a "
            "different record_id before writing the reviewed decision."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.cluster_report.exists():
        print(f"Cluster report not found: {args.cluster_report}", file=sys.stderr)
        return 2

    report = json.loads(args.cluster_report.read_text())
    if args.override_record_id and not args.replace_program_dsld_conflicts:
        print(
            "--override-record-id requires --replace-program-dsld-conflicts "
            "so older wrong-row decisions cannot shadow the alternate row",
            file=sys.stderr,
        )
        return 2
    try:
        cluster = find_cluster(
            report.get("clusters") or [],
            program=args.program,
            record_id=args.record_id,
        )
        entries = generate_reviewed_overrides(
            cluster,
            action=args.action,
            review_note=args.review_note,
            reviewer=args.reviewer,
            review_source=args.review_source,
            member_dsld_ids=set(args.member_dsld_id) if args.member_dsld_id else None,
            override_record_id=args.override_record_id,
            override_matched_brand=args.override_matched_brand,
            override_matched_product=args.override_matched_product,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        f"Prepared {len(entries)} {args.action} override entries for "
        f"{cluster.get('program')} / {cluster.get('record_id')}"
    )
    if args.member_dsld_id:
        print(f"  Limited to DSLD IDs: {', '.join(args.member_dsld_id)}")

    if args.dry_run:
        print("  (dry-run — overrides file NOT modified)")
        return 0

    added, replaced, removed_conflicts = merge_reviewed_into_overrides_file(
        args.overrides_path,
        entries,
        replace_program_dsld_conflicts=args.replace_program_dsld_conflicts,
    )
    print(f"  Wrote {added} new override entries to {args.overrides_path}")
    if replaced:
        print(f"  Replaced {replaced} existing reviewed/pending entries")
    if removed_conflicts:
        print(f"  Removed {removed_conflicts} conflicting same-program/dsld entries")
    print(f"  (skipped {len(entries) - added - replaced} duplicates already in file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
