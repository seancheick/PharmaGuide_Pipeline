"""Single v4-native scored-artifact assembler.

This is the only production seam allowed to turn one enriched product into a
Stage-3 scored artifact. Scoring modules calculate rubric results; this module
owns the cross-cutting artifact contract: coverage diagnostics, strict input
contract, public verdict precedence, compatibility score mirrors, and
provenance. It never invokes or copies the retired /80 scorer.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict

from score_supplements_v4 import score_product_v4
from scoring_input_contract import get_scoring_ingredients, scoring_input_scope
from supplement_taxonomy import percentile_label_for


SCORED_ARTIFACT_SCHEMA_VERSION = "4.3.0"
LOW_COVERAGE_TRUST_FLOOR = 0.3


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _display_score(value: Any, status: Any) -> str:
    if status != "scored":
        return "N/A"
    try:
        score = float(value)
        if not math.isfinite(score):
            return "N/A"
        return f"{math.floor(score + 0.5)}/100"
    except (TypeError, ValueError):
        return "N/A"


def _config_fingerprint(provenance: Dict[str, Any]) -> str | None:
    versions = provenance.get("config_versions")
    if versions is None:
        return None
    return json.dumps(versions, sort_keys=True, ensure_ascii=False)


def _inactive_penalty_details(module_breakdown: Any) -> list[Dict[str, Any]]:
    dimensions = _safe_dict(_safe_dict(module_breakdown).get("dimensions"))
    formulation = _safe_dict(dimensions.get("formulation"))
    metadata = _safe_dict(formulation.get("metadata"))
    raw_details = metadata.get("inactive_penalty_details")
    if not isinstance(raw_details, list):
        return []
    return [dict(item) for item in raw_details if isinstance(item, dict)]


def _public_verdict(v4: Dict[str, Any], mapped_coverage: float) -> str:
    """Resolve public verdict precedence, including the data-trust floor."""
    status = str(v4.get("quality_score_status") or "")
    verdict = str(v4.get("v4_verdict") or "").upper()
    if status == "suppressed_safety":
        return verdict if verdict in {"BLOCKED", "UNSAFE"} else "BLOCKED"
    if status == "not_scored":
        return "NOT_SCORED"
    if status != "scored":
        return "NOT_SCORED"
    if verdict in {"BLOCKED", "UNSAFE", "CAUTION", "POOR"}:
        return verdict
    if mapped_coverage < LOW_COVERAGE_TRUST_FLOOR:
        return "CAUTION"
    return "SAFE"


def _product_safety_status(
    safety_gate: Dict[str, Any],
    *,
    was_assessed: bool,
) -> str:
    """Project only catalog safety-gate policy into the consumer safety state.

    Legacy verdict also carries quality and coverage policy (POOR and the
    low-coverage CAUTION), so it must never be the source for this field.
    """
    if not was_assessed:
        return "not_assessed"
    verdict = str(safety_gate.get("verdict") or "").upper()
    if verdict == "BLOCKED":
        return "blocked"
    if verdict == "UNSAFE":
        return "unsafe"
    if verdict == "CAUTION":
        return "caution"
    if verdict in {"", "SAFE"}:
        return "no_known_catalog_concern"
    return "not_assessed"


#: Public Evidence display states that mean PharmaGuide has NOT performed the
#: review, as opposed to having performed it and reached a conclusion. The
#: display-state vocabulary is owned by quality_score.evidence_display_state;
#: this reads it rather than re-deriving completion from result-state strings.
#:
#: "applicability_unestablished" is deliberately absent: records WERE found and
#: reviewed, and failing to establish applicability to this label is itself a
#: completed product-level conclusion.
UNASSESSED_EVIDENCE_DISPLAY_STATES = frozenset({"not_yet_reviewed"})


def _quality_assessment_status(
    quality_score_status: str,
    dose_safety: Dict[str, Any],
    pillars: Dict[str, Any] | None = None,
) -> str:
    """Report whether the assessment the rubric REQUIRES actually completed.

    This answers a different question from ``quality_score_status``, and the two
    must not be collapsed:

      quality_score_status       did the engine produce a usable number?
      quality_assessment_status  did PharmaGuide finish the assessment?

    Both facts are real and independent. The engine can compute 54 out of 100
    while the Evidence pillar contributing 0 of those points was never reviewed
    at all - 4,117 products in the 2026.09.19 catalog are exactly that. Those
    products are honestly ``scored`` AND honestly ``partial``; the number exists,
    the judgement does not. Collapsing them cost 3,661 products a published tier
    that the assessed pillars could not support, because the true total lay
    anywhere in a 20-point band straddling a tier boundary.

    A pillar carrying 0 because it was never assessed is not the same as a
    pillar carrying 0 because the review concluded zero. Only the first makes
    the assessment incomplete.
    """
    state_counts = _safe_dict(dose_safety.get("state_counts"))
    unresolved = state_counts.get("material_but_unresolved", 0)
    if (
        isinstance(unresolved, (int, float))
        and not isinstance(unresolved, bool)
        and unresolved > 0
    ):
        return "partial"
    # A required rubric dimension that was never reviewed leaves the assessment
    # incomplete no matter how strong the other five are. A weak five-pillar
    # profile does not make the sixth pillar assessed.
    evidence = _safe_dict(_safe_dict(pillars).get("evidence"))
    if evidence.get("display_state") in UNASSESSED_EVIDENCE_DISPLAY_STATES:
        return "partial"
    if quality_score_status in {"scored", "suppressed_safety"}:
        return "complete"
    if quality_score_status == "not_scored":
        # Audited 2026-09-19 over the 255 not_scored artifacts:
        #   243 blocked_by_completeness_gate  - incomplete product data, so the
        #       assessment genuinely could not be completed. partial is correct.
        #     3 safety_policy_review_required - awaiting human review. correct.
        #     9 intentional_non_scoreable_product - deliberately out of scope.
        #       Neither incomplete nor failed; the vocabulary has no
        #       "not_applicable", and inventing a fourth value to carry nine
        #       products would be worse than this documented imprecision. These
        #       never reach the catalog: the export gate quarantines every
        #       not_scored product.
        return "partial"
    return "failed"


def assemble_scored_artifact(
    enriched_product: Dict[str, Any],
    v4: Dict[str, Any],
) -> Dict[str, Any]:
    """Project an already-calculated v4 result into the Stage-3 contract.

    This pure projection seam exists for scorer/assembler contract tests. The
    production entry point remains :func:`build_scored_artifact`, which obtains
    the v4 result itself and guarantees exactly one scoring pass.
    """
    if not isinstance(enriched_product, dict):
        raise TypeError("enriched product must be an object")
    if not isinstance(v4, dict):
        raise TypeError("v4 scoring result must be an object")

    scoring_input = get_scoring_ingredients(
        enriched_product,
        strict=True,
        allow_legacy_fallback=False,
    )
    diagnostics = scoring_input.diagnostics()
    mapped_coverage = float(scoring_input.mapped_coverage or 0.0)

    breakdown = _safe_dict(v4.get("v4_breakdown"))
    raw_safety_gate = breakdown.get("safety_gate")
    safety_gate = _safe_dict(raw_safety_gate)
    safety_was_assessed = (
        isinstance(raw_safety_gate, dict) and "verdict" in raw_safety_gate
    )
    completeness_gate = _safe_dict(breakdown.get("completeness_gate"))
    assessment_readiness = _safe_dict(breakdown.get("assessment_readiness"))
    dose_safety = _safe_dict(breakdown.get("dose_safety"))
    provenance = _safe_dict(breakdown.get("provenance"))
    module_breakdown = breakdown.get("module")

    gate_coverage = completeness_gate.get("mapped_coverage")
    try:
        gate_coverage_number = float(gate_coverage)
    except (TypeError, ValueError):
        gate_coverage_number = mapped_coverage
    if abs(gate_coverage_number - mapped_coverage) > 0.0001:
        raise RuntimeError(
            "v4 completeness coverage diverged from the shared scoring-input contract"
        )

    status = str(v4.get("quality_score_status") or "not_scored")
    raw_score_confidence = (
        v4.get("quality_score_confidence")
        if "quality_score_confidence" in v4
        else v4.get("v4_confidence")
    )
    score_confidence = (
        str(raw_score_confidence).strip().lower()
        if raw_score_confidence is not None
        else None
    )
    if score_confidence not in {"high", "moderate", "low"}:
        score_confidence = None
    score_unavailable_reason = v4.get("score_unavailable_reason")
    product_safety_status = _product_safety_status(
        safety_gate,
        was_assessed=safety_was_assessed,
    )
    quality_assessment_status = _quality_assessment_status(
        status, dose_safety, v4.get("quality_pillars_v4")
    )
    quality_score = v4.get("quality_score_v4_100")
    verdict = _public_verdict(v4, mapped_coverage)
    safety_verdict = str(safety_gate.get("verdict") or "SAFE").upper()
    safety_decision = _safe_dict(safety_gate.get("safety_decision"))
    safety_review_records = list(safety_gate.get("review_records") or [])
    decision_reason = safety_decision.get("reason_code")
    blocking_reason = (
        decision_reason or safety_gate.get("blocking_reason")
        if safety_verdict in {"BLOCKED", "UNSAFE"}
        else None
    )
    safety_signals = list(safety_gate.get("safety_signals") or [])
    if verdict == "CAUTION" and mapped_coverage < LOW_COVERAGE_TRUST_FLOOR:
        safety_signals = list(dict.fromkeys(safety_signals + ["low_mapped_coverage"]))

    taxonomy = dict(_safe_dict(enriched_product.get("supplement_taxonomy")))
    percentile_category = taxonomy.get("percentile_category")
    strict_contract = dict(diagnostics["strict_scoring_contract"])
    scored_at = datetime.now(timezone.utc).isoformat()
    config_fingerprint = _config_fingerprint(provenance)
    classification = _safe_dict(
        enriched_product.get("product_scoring_classification")
    )
    route_decision = dict(_safe_dict(classification.get("route_decision")))
    route_confidence = (
        route_decision.get("confidence")
        if route_decision
        else classification.get("route_confidence")
    )
    if route_decision and route_decision.get("module") != v4.get("v4_module"):
        raise RuntimeError(
            "canonical route decision diverged from the scoring module"
        )

    artifact: Dict[str, Any] = {
        "dsld_id": enriched_product.get("dsld_id"),
        "product_name": enriched_product.get("product_name"),
        "brand_name": enriched_product.get("brand_name") or enriched_product.get("brandName"),
        "evaluation_stage": "scored_v4",
        "output_schema_version": SCORED_ARTIFACT_SCHEMA_VERSION,
        "score_basis": "v4_six_pillar",
        "not_scorable_reason": (
            (
                completeness_gate.get("reason")
                or score_unavailable_reason
            )
            if status == "not_scored"
            else None
        ),
        "supplement_taxonomy": taxonomy,
        "primary_type": taxonomy.get("primary_type"),
        "secondary_type": taxonomy.get("secondary_type"),
        "percentile_category": taxonomy.get("percentile_category"),
        "category_percentile": {
            "category_key": percentile_category,
            "category_label": percentile_label_for(percentile_category),
        },
        "mapped_coverage": round(mapped_coverage, 4),
        "unmapped_actives": list(scoring_input.unmapped_actives),
        "unmapped_actives_total": scoring_input.unmapped_count,
        "unmapped_actives_excluding_banned_exact_alias": scoring_input.unmapped_count,
        "scoring_ingredients_source": scoring_input.source,
        "scoring_fallbacks_used": diagnostics["scoring_fallbacks_used"],
        "iqd_contract_diagnostics": diagnostics,
        "strict_scoring_contract": strict_contract,
        "verdict": verdict,
        "safety_verdict": safety_verdict,
        "blocking_reason": blocking_reason,
        "safety_signal_reason": decision_reason or (
            safety_signals[0] if safety_signals else None
        ),
        "safety_decision": safety_decision or None,
        "safety_review_records": safety_review_records,
        "flags": safety_signals,
        "badges": [],
        "quality_score_v4_100": quality_score,
        "quality_score_status": status,
        "quality_score_confidence": score_confidence,
        "score_unavailable_reason": score_unavailable_reason,
        "route_decision": route_decision or None,
        "route_confidence": route_confidence,
        "product_safety_status": product_safety_status,
        "quality_assessment_status": quality_assessment_status,
        "assessment_readiness": assessment_readiness,
        "dose_safety_evaluation": dose_safety,
        "quality_tier": v4.get("quality_tier"),
        "quality_score_suppressed_reason": v4.get("quality_score_suppressed_reason"),
        "raw_score_v4_100": v4.get("raw_score_v4_100"),
        "quality_pillars_v4": v4.get("quality_pillars_v4"),
        "score_100_equivalent": quality_score,
        "display_100": _display_score(quality_score, status),
        "grade": v4.get("quality_tier"),
        # Provenance only: every other fact lives once at the top level.
        "scoring_metadata": {
            "scoring_version": provenance.get("scoring_engine_version"),
            "scored_date": scored_at,
        },
        "_score_model_version": "v4",
        "_v4_module": v4.get("v4_module"),
        "_v4_module_breakdown": module_breakdown,
        "_v4_inactive_penalty_details": _inactive_penalty_details(
            module_breakdown
        ),
        "_v4_confidence_detail": breakdown.get("confidence"),
        "_v4_quality_version": v4.get("quality_score_version"),
        "_v4_clean_label_flags": v4.get("clean_label_flags_v4"),
        "_v4_safety_gate": safety_gate,
        "_v4_completeness_gate": completeness_gate,
        "_v4_provenance": provenance,
        "_v4_config_fingerprint": config_fingerprint,
    }
    return artifact


def build_scored_artifact(enriched_product: Dict[str, Any]) -> Dict[str, Any]:
    """Return the complete v4 Stage-3 artifact for one enriched product.

    Malformed top-level input raises so the batch owner can fail the file and
    withhold its manifest. Product-level incompleteness is represented by the
    typed ``not_scored`` contract instead of an exception or guessed score.
    """
    if not isinstance(enriched_product, dict):
        raise TypeError("enriched product must be an object")
    # Router, modules, gates, confidence, and assembly all consume the same
    # contract. Build it once per strictness variant for this product instead
    # of repeatedly deriving and regex-scanning identical evidence rows.
    with scoring_input_scope(enriched_product):
        return assemble_scored_artifact(
            enriched_product,
            score_product_v4(enriched_product),
        )


