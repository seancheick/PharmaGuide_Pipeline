"""Exact product-set baseline reconstruction for route review."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _finish_report(features: list[dict]) -> dict:
    report = {"report_schema_version": "1.0.0", "features": features}
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return report


def test_snapshot_baseline_uses_candidate_product_set_and_shipped_routes() -> None:
    from audits.routing_snapshot_baseline import build_snapshot_baseline

    candidate = _finish_report([
        {"dsld_id": "1", "recomputed_route": "sports"},
        {"dsld_id": "2", "recomputed_route": "generic"},
    ])
    snapshot = {
        "integrity": {"snapshot_sha256": "a" * 64},
        "products": {
            "1": {"route": {"module": "generic"}},
            "2": {"route": {"module": "fiber_digestive"}},
        },
    }

    report = build_snapshot_baseline(candidate, snapshot)

    assert report["product_count"] == 2
    assert report["route_distribution"] == {
        "fiber_digestive": 1,
        "generic": 1,
    }
    assert report["source_snapshot_sha256"] == "a" * 64
    assert report["features"] == [
        {"dsld_id": "1", "recomputed_route": "generic"},
        {"dsld_id": "2", "recomputed_route": "fiber_digestive"},
    ]
    assert len(report["report_sha256"]) == 64


def test_snapshot_baseline_rejects_product_set_drift() -> None:
    from audits.routing_snapshot_baseline import RoutingSnapshotBaselineError
    from audits.routing_snapshot_baseline import build_snapshot_baseline

    candidate = _finish_report([{"dsld_id": "1", "recomputed_route": "generic"}])
    snapshot = {"products": {"2": {"route": {"module": "generic"}}}}

    with pytest.raises(RoutingSnapshotBaselineError, match="product sets differ"):
        build_snapshot_baseline(candidate, snapshot)
