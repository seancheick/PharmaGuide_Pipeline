#!/usr/bin/env python3
"""Reconstruct an exact-product-set route baseline from a scoring snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REPORT_SCHEMA_VERSION = "1.0.0"


class RoutingSnapshotBaselineError(RuntimeError):
    """The candidate shadow and shipped scoring snapshot do not align."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _verified_report_hash(report: Mapping[str, Any]) -> str:
    claimed = str(report.get("report_sha256") or "")
    body = dict(report)
    body.pop("report_sha256", None)
    actual = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    if claimed != actual:
        raise RoutingSnapshotBaselineError(
            f"candidate routing shadow self-hash mismatch: claimed={claimed} actual={actual}"
        )
    return actual


def build_snapshot_baseline(
    candidate: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Return compact shipped routes aligned to the candidate's exact IDs."""
    candidate_hash = _verified_report_hash(candidate)
    candidate_ids = [
        str(row.get("dsld_id") or "").strip()
        for row in candidate.get("features") or []
        if isinstance(row, Mapping)
    ]
    if not all(candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
        raise RoutingSnapshotBaselineError(
            "candidate routing shadow has missing or duplicate product IDs"
        )

    products = snapshot.get("products")
    products = products if isinstance(products, Mapping) else {}
    snapshot_ids = {str(value) for value in products}
    if set(candidate_ids) != snapshot_ids:
        missing = sorted(set(candidate_ids) - snapshot_ids)
        extra = sorted(snapshot_ids - set(candidate_ids))
        raise RoutingSnapshotBaselineError(
            "candidate and snapshot product sets differ: "
            f"missing_from_snapshot={len(missing)} extra_in_snapshot={len(extra)}"
        )

    route_counts: Counter[str] = Counter()
    features: list[dict[str, str]] = []
    for dsld_id in sorted(candidate_ids, key=lambda value: (len(value), value)):
        product = products.get(dsld_id)
        product = product if isinstance(product, Mapping) else {}
        route = product.get("route")
        route = route if isinstance(route, Mapping) else {}
        module = str(route.get("module") or "generic").strip().lower()
        if not module:
            raise RoutingSnapshotBaselineError(
                f"snapshot product {dsld_id} has no route module"
            )
        route_counts[module] += 1
        features.append({"dsld_id": dsld_id, "recomputed_route": module})

    integrity = snapshot.get("integrity")
    integrity = integrity if isinstance(integrity, Mapping) else {}
    source_hash = str(
        integrity.get("sha256") or integrity.get("snapshot_sha256") or ""
    ) or None
    report: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "mode": "reconstructed_shipped_baseline",
        "candidate_report_sha256": candidate_hash,
        "source_snapshot_sha256": source_hash,
        "product_count": len(features),
        "route_distribution": dict(sorted(route_counts.items())),
        "features": features,
    }
    report["report_sha256"] = hashlib.sha256(_canonical_bytes(report)).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    report = build_snapshot_baseline(candidate, snapshot)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Reconstructed {report['product_count']} shipped routes at "
        f"{output} ({report['report_sha256']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
