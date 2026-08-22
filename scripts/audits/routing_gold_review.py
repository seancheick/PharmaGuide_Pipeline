#!/usr/bin/env python3
"""Bind and review every route change between two routing feature shadows."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


class RoutingGoldReviewError(RuntimeError):
    """The exact reviewed route candidate could not be reproduced."""


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
        raise RoutingGoldReviewError(
            f"routing shadow self-hash mismatch: claimed={claimed} actual={actual}"
        )
    return actual


def _feature_index(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for feature in report.get("features") or []:
        if not isinstance(feature, Mapping):
            raise RoutingGoldReviewError("routing shadow contains a non-object feature")
        dsld_id = str(feature.get("dsld_id") or "").strip()
        if not dsld_id or dsld_id in index:
            raise RoutingGoldReviewError(
                f"routing shadow has missing or duplicate dsld_id: {dsld_id!r}"
            )
        index[dsld_id] = feature
    return index


def _review_group(
    dsld_id: str,
    old_route: str,
    new_route: str,
    feature: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> tuple[str, str]:
    reason = str(feature.get("route_reason") or "")
    if new_route == "probiotic":
        reviewed = {
            str(value) for value in lock.get("manual_probiotic_reviews") or []
        }
        if dsld_id not in reviewed:
            raise RoutingGoldReviewError(
                f"{dsld_id}: probiotic promotion lacks an explicit manual review"
            )
        if (
            reason != "profile_content:probiotic"
            or feature.get("probiotic_is_product") is not True
            or int(feature.get("probiotic_strain_count") or 0) < 1
            or int(feature.get("probiotic_named_identity_count") or 0) < 1
        ):
            raise RoutingGoldReviewError(
                f"{dsld_id}: probiotic promotion lacks typed strain identity"
            )
        if (
            feature.get("probiotic_has_cfu") is not True
            or (
                float(feature.get("probiotic_total_cfu") or 0.0) <= 0
                and float(feature.get("probiotic_total_billion_count") or 0.0) <= 0
            )
        ):
            raise RoutingGoldReviewError(
                f"{dsld_id}: probiotic promotion lacks a positive typed CFU total"
            )
        return (
            "typed_probiotic_intent",
            "Explicitly reviewed probiotic product with named strain identity and a positive typed CFU total.",
        )

    if new_route == "sports":
        protein_mass = float(feature.get("protein_mass_mg") or 0.0)
        if feature.get("protein_title_intent") and protein_mass > 0:
            return "protein_intent_and_mass", "Explicit protein/mass-gainer intent with disclosed protein mass."
        threshold_review = (
            (lock.get("threshold_reviews") or {}).get(
                "material_row_level_protein_mg"
            )
            or {}
        )
        selected_threshold = float(
            threshold_review.get("selected_threshold") or 0.0
        )
        row_level_mass = float(
            feature.get("row_level_protein_mass_mg") or 0.0
        )
        if selected_threshold > 0 and row_level_mass >= selected_threshold:
            return (
                "material_row_level_protein",
                "Reviewed material Protein declaration at the zero-false-positive corpus boundary.",
            )
        raise RoutingGoldReviewError(
            f"{dsld_id}: sports promotion lacks reviewed protein intent or row-level mass"
        )

    if new_route == "b_complex":
        if (
            not feature.get("title_b_complex_intent")
            or reason != "explicit_b_complex_panel"
            or int(feature.get("b_vitamin_count") or 0) < 3
            or float(feature.get("b_family_identity_share") or 0.0) < 0.615385
        ):
            raise RoutingGoldReviewError(
                f"{dsld_id}: B-complex promotion is outside the reviewed intent boundary"
            )
        return "explicit_b_complex_intent", "Reviewed B-label intent and measured B-family panel boundary."

    if new_route == "fiber_digestive":
        checks = {
            "fiber_title_intent": bool(feature.get("title_fiber_intent")),
            "digestive_product_intent": bool(feature.get("title_digestive_intent")),
            "digestive_enzyme_context": bool(feature.get("digestive_enzyme_context")),
            "declared_fiber_blend_intent": bool(feature.get("declared_fiber_blend_intent")),
            "material_fiber_panel": float(feature.get("fiber_mass_share") or 0.0) >= 0.753769,
        }
        if not checks.get(reason, False):
            raise RoutingGoldReviewError(
                f"{dsld_id}: fiber/digestive promotion lacks its reviewed intent fact ({reason})"
            )
        return f"fiber_digestive:{reason}", "Explicit label intent, declared blend intent, or reviewed material fiber boundary."

    if new_route == "generic" and reason == "protein_intent_evidence_missing":
        reviewed = {
            str(value) for value in lock.get("manual_quarantine_reviews") or []
        }
        if dsld_id not in reviewed:
            raise RoutingGoldReviewError(
                f"{dsld_id}: unresolved protein intent lacks an explicit quarantine review"
            )
        return (
            "quarantine_unresolved_protein_intent",
            "Explicit protein or mass-gainer intent has no supporting identity or dose and is quarantined.",
        )

    if new_route == "generic" and old_route == "fiber_digestive":
        if (
            feature.get("title_fiber_intent")
            or feature.get("title_digestive_intent")
            or feature.get("declared_fiber_blend_intent")
        ):
            raise RoutingGoldReviewError(
                f"{dsld_id}: fiber demotion still has explicit fiber/digestive intent"
            )
        return "remove_incidental_fiber_or_systemic_enzyme_route", "No reviewed specialized intent; incidental category/fiber or systemic/dual-use enzyme evidence is generic."

    if new_route == "generic" and old_route in {"b_complex", "multi_or_prenatal"}:
        reviewed = set(
            str(value)
            for value in (
                (lock.get("manual_generic_reviews") or {}).get(old_route) or []
            )
        )
        if dsld_id not in reviewed:
            raise RoutingGoldReviewError(
                f"{dsld_id}: {old_route}->generic lacks an explicit manual review"
            )
        return f"manual_generic:{old_route}", "Reviewed product intent does not support the former specialized route."

    raise RoutingGoldReviewError(
        f"{dsld_id}: unreviewed route transition {old_route}->{new_route}"
    )


def build_gold_review(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a fail-closed review record for every changed product."""
    baseline_hash = _verified_report_hash(baseline)
    candidate_hash = _verified_report_hash(candidate)
    if baseline_hash != lock.get("baseline_report_sha256"):
        raise RoutingGoldReviewError("baseline routing shadow is not the reviewed hash")
    if candidate_hash != lock.get("candidate_report_sha256"):
        raise RoutingGoldReviewError("candidate routing shadow is not the reviewed hash")

    before = _feature_index(baseline)
    after = _feature_index(candidate)
    if set(before) != set(after):
        raise RoutingGoldReviewError("baseline and candidate product sets differ")

    changes: list[dict[str, Any]] = []
    transition_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    for dsld_id in sorted(before, key=lambda value: (len(value), value)):
        old_route = str(before[dsld_id].get("recomputed_route") or "generic")
        new_route = str(after[dsld_id].get("recomputed_route") or "generic")
        if old_route == new_route:
            continue
        feature = after[dsld_id]
        group, rationale = _review_group(
            dsld_id,
            old_route,
            new_route,
            feature,
            lock,
        )
        transition = f"{old_route}->{new_route}"
        transition_counts[transition] += 1
        group_counts[group] += 1
        changes.append({
            "dsld_id": dsld_id,
            "product_name": feature.get("product_name"),
            "brand_name": feature.get("brand_name"),
            "old_route": old_route,
            "expected_route": new_route,
            "route_reason": feature.get("route_reason"),
            "reviewed": True,
            "review_group": group,
            "review_rationale": rationale,
        })

    expected_count = int(lock.get("expected_changed_count") or -1)
    expected_transitions = dict(lock.get("expected_transition_counts") or {})
    actual_transitions = dict(sorted(transition_counts.items()))
    if len(changes) != expected_count:
        raise RoutingGoldReviewError(
            f"reviewed change count drifted: expected={expected_count} actual={len(changes)}"
        )
    if actual_transitions != expected_transitions:
        raise RoutingGoldReviewError(
            f"reviewed transition counts drifted: {actual_transitions}"
        )

    report: dict[str, Any] = {
        "report_schema_version": "1.0.0",
        "mode": "review_only",
        "baseline_report_sha256": baseline_hash,
        "candidate_report_sha256": candidate_hash,
        "reviewed_change_count": len(changes),
        "unreviewed_change_count": 0,
        "transition_counts": actual_transitions,
        "review_group_counts": dict(sorted(group_counts.items())),
        "threshold_reviews": lock.get("threshold_reviews"),
        "changes": changes,
    }
    report["report_sha256"] = hashlib.sha256(_canonical_bytes(report)).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument(
        "--lock",
        default=str(Path(__file__).with_name("routing_review_lock_v2.json")),
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    report = build_gold_review(baseline, candidate, lock)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Reviewed {report['reviewed_change_count']} route changes; "
        f"unreviewed={report['unreviewed_change_count']} ({report['report_sha256']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
