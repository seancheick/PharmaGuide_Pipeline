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


def test_gold_review_accepts_reviewed_row_level_protein_boundary() -> None:
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "multi_or_prenatal"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Reviewed Protein Shake",
            "recomputed_route": "sports",
            "route_reason": "profile_content:sports",
            "protein_title_intent": False,
            "protein_mass_mg": 25_000,
            "row_level_protein_mass_mg": 20_000,
        },
    ])
    lock = _lock(baseline, candidate, "multi_or_prenatal->sports")
    lock["threshold_reviews"] = {
        "material_row_level_protein_mg": {"selected_threshold": 20_000.0}
    }

    report = build_gold_review(baseline, candidate, lock)

    assert report["changes"][0]["review_group"] == (
        "material_row_level_protein"
    )


def test_gold_review_accepts_explicit_preworkout_with_observed_formula() -> None:
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "generic"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Opaque Brand Fruit Punch",
            "recomputed_route": "sports",
            "route_reason": "profile_content:sports",
            "explicit_preworkout_statement": True,
            "observed_sports_identity_count": 2,
            "observed_sports_canonical_ids": [
                "creatine_monohydrate",
                "l_citrulline",
            ],
        },
    ])

    report = build_gold_review(
        baseline,
        candidate,
        _lock(baseline, candidate, "generic->sports"),
    )

    assert report["changes"][0]["review_group"] == (
        "explicit_preworkout_with_observed_formula"
    )


def test_gold_review_accepts_explicit_omega_with_observed_epa_dha() -> None:
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "generic"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Omega-3 Gummies",
            "recomputed_route": "omega",
            "route_reason": "taxonomy:general_supplement:omega_evidence_override",
            "title_omega_intent": True,
            "observed_omega_canonical_ids": ["dha", "epa"],
        },
    ])

    report = build_gold_review(
        baseline,
        candidate,
        _lock(baseline, candidate, "generic->omega"),
    )

    assert report["changes"][0]["review_group"] == (
        "explicit_omega_with_observed_epa_dha"
    )


def test_gold_review_rejects_blend_mass_as_material_protein_boundary() -> None:
    from audits.routing_gold_review import RoutingGoldReviewError
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "multi_or_prenatal"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Daily Multi Shake",
            "recomputed_route": "sports",
            "route_reason": "profile_content:sports",
            "protein_title_intent": False,
            "protein_mass_mg": 25_000,
            "row_level_protein_mass_mg": 0,
        },
    ])
    lock = _lock(baseline, candidate, "multi_or_prenatal->sports")
    lock["threshold_reviews"] = {
        "material_row_level_protein_mg": {"selected_threshold": 20_000.0}
    }

    with pytest.raises(RoutingGoldReviewError, match="protein intent or row-level mass"):
        build_gold_review(baseline, candidate, lock)


def test_gold_review_accepts_typed_digestive_enzyme_context() -> None:
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "generic"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Digestive Enzyme Formula",
            "recomputed_route": "fiber_digestive",
            "route_reason": "digestive_enzyme_context",
            "digestive_enzyme_context": True,
        },
    ])

    report = build_gold_review(
        baseline,
        candidate,
        _lock(baseline, candidate, "generic->fiber_digestive"),
    )

    assert report["changes"][0]["review_group"] == (
        "fiber_digestive:digestive_enzyme_context"
    )


def test_gold_review_requires_explicit_review_for_unresolved_protein_intent() -> None:
    from audits.routing_gold_review import RoutingGoldReviewError
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "fiber_digestive"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Keto Protein",
            "recomputed_route": "generic",
            "route_reason": "protein_intent_evidence_missing",
            "title_fiber_intent": False,
            "title_digestive_intent": False,
            "declared_fiber_blend_intent": False,
        },
    ])
    lock = _lock(baseline, candidate, "fiber_digestive->generic")

    with pytest.raises(RoutingGoldReviewError, match="explicit quarantine review"):
        build_gold_review(baseline, candidate, lock)

    lock["manual_quarantine_reviews"] = ["P1"]
    report = build_gold_review(baseline, candidate, lock)
    assert report["changes"][0]["review_group"] == (
        "quarantine_unresolved_protein_intent"
    )


def test_gold_review_requires_explicit_review_and_typed_probiotic_evidence() -> None:
    from audits.routing_gold_review import RoutingGoldReviewError
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "multi_or_prenatal"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "product_name": "Kids Multi + Probiotic",
            "recomputed_route": "probiotic",
            "route_reason": "profile_content:probiotic",
            "probiotic_is_product": True,
            "probiotic_strain_count": 1,
            "probiotic_named_identity_count": 1,
            "probiotic_has_cfu": True,
            "probiotic_total_cfu": 250_000_000,
        },
    ])
    lock = _lock(baseline, candidate, "multi_or_prenatal->probiotic")

    with pytest.raises(RoutingGoldReviewError, match="explicit manual review"):
        build_gold_review(baseline, candidate, lock)

    lock["manual_probiotic_reviews"] = ["P1"]
    report = build_gold_review(baseline, candidate, lock)

    assert report["reviewed_change_count"] == 1
    assert report["changes"][0]["review_group"] == "typed_probiotic_intent"


def test_gold_review_rejects_probiotic_promotion_without_typed_identity() -> None:
    from audits.routing_gold_review import RoutingGoldReviewError
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([
        {"dsld_id": "P1", "recomputed_route": "fiber_digestive"},
    ])
    candidate = _finish_report([
        {
            "dsld_id": "P1",
            "recomputed_route": "probiotic",
            "route_reason": "profile_content:probiotic",
            "probiotic_is_product": True,
            "probiotic_strain_count": 0,
            "probiotic_named_identity_count": 0,
            "probiotic_has_cfu": True,
            "probiotic_total_cfu": 5_000_000_000,
        },
    ])
    lock = _lock(baseline, candidate, "fiber_digestive->probiotic")
    lock["manual_probiotic_reviews"] = ["P1"]

    with pytest.raises(RoutingGoldReviewError, match="typed strain identity"):
        build_gold_review(baseline, candidate, lock)


def test_gold_review_rejects_unreviewed_transition() -> None:
    from audits.routing_gold_review import RoutingGoldReviewError
    from audits.routing_gold_review import build_gold_review

    baseline = _finish_report([{"dsld_id": "P1", "recomputed_route": "generic"}])
    candidate = _finish_report([{"dsld_id": "P1", "recomputed_route": "omega"}])

    with pytest.raises(
        RoutingGoldReviewError,
        match="omega promotion lacks explicit title intent",
    ):
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
        (SCRIPTS_ROOT / "audits" / "routing_review_lock_v2.json").read_text()
    )
    thresholds = lock["threshold_reviews"]

    assert contract._ROUTE_B_EXPLICIT_MIN_FAMILY_SHARE == thresholds[
        "explicit_b_family_share"
    ]["selected_threshold"]
    assert contract._ROUTE_FIBER_MATERIAL_MIN_MASS_SHARE == thresholds[
        "material_fiber_mass_share"
    ]["selected_threshold"]
    assert contract._ROUTE_DIGESTIVE_ENZYME_MIN_IDENTITY_SHARE == thresholds[
        "digestive_enzyme_identity_share"
    ]["selected_threshold"]
    assert contract._ROUTE_PROTEIN_MATERIAL_MIN_MG == thresholds[
        "material_row_level_protein_mg"
    ]["selected_threshold"]
    assert thresholds["inferred_multivitamin"]["selected_threshold"] is None
