"""Fail-closed routing-gold review contracts."""

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
    report = {"features": features}
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return report


def _lock(baseline: dict, candidate: dict, transition: str) -> dict:
    return {
        "baseline_report_sha256": baseline["report_sha256"],
        "candidate_report_sha256": candidate["report_sha256"],
        "expected_changed_count": 1,
        "expected_transition_counts": {transition: 1},
        "manual_generic_reviews": {},
    }


def test_gold_review_assigns_every_supported_change() -> None:
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "generic"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Plant Protein",
            "recomputed_route": "sports",
            "route_reason": "profile_content:sports",
            "protein_title_intent": True,
            "protein_mass_mg": 20_000,
        },
    ])

    report = build_gold_review(
        baseline,
        candidate,
        _lock(baseline, candidate, "generic->sports"),
    )

    assert report["reviewed_change_count"] == 1
    assert report["unreviewed_change_count"] == 0
    assert report["changes"][0]["review_group"] == "protein_intent_and_mass"
    assert report["changes"][0]["expected_route"] == "sports"


def test_gold_review_rejects_unreviewed_transition() -> None:
    from audits.routing_gold_review import RoutingGoldReviewError
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([{"dsld_id": "P1", "recomputed_route": "generic"}])
    candidate = _finish_report([{"dsld_id": "P1", "recomputed_route": "omega"}])

    with pytest.raises(RoutingGoldReviewError, match="unreviewed route transition"):
        build_gold_review(
            baseline,
            candidate,
            _lock(baseline, candidate, "generic->omega"),
        )


def test_gold_review_rejects_candidate_hash_drift() -> None:
    from audits.routing_gold_review import RoutingGoldReviewError
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([{"dsld_id": "P1", "recomputed_route": "generic"}])
    candidate = _finish_report([{"dsld_id": "P1", "recomputed_route": "generic"}])
    lock = _lock(baseline, candidate, "generic->generic")
    lock["candidate_report_sha256"] = "0" * 64

    with pytest.raises(RoutingGoldReviewError, match="candidate routing shadow"):
        build_gold_review(baseline, candidate, lock)


def test_review_lock_matches_production_thresholds() -> None:
    import scoring_input_contract as contract

    lock = json.loads(
        (SCRIPTS_ROOT / "audits" / "routing_review_lock_v1.json").read_text()
    )
    thresholds = lock["threshold_reviews"]

    assert contract._ROUTE_B_EXPLICIT_MIN_FAMILY_SHARE == thresholds[
        "explicit_b_family_share"
    ]["selected_threshold"]
    assert contract._ROUTE_FIBER_MATERIAL_MIN_MASS_SHARE == thresholds[
        "material_fiber_mass_share"
    ]["selected_threshold"]
    assert thresholds["inferred_multivitamin"]["selected_threshold"] is None
