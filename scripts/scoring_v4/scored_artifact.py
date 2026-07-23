"""Single v4-native scored-artifact assembler.

This is the only production seam allowed to turn one enriched product into a
Stage-3 scored artifact. Scoring modules calculate rubric results; this module
owns the cross-cutting artifact contract: coverage diagnostics, strict input
contract, public verdict precedence, compatibility score mirrors, and
provenance. It never invokes or copies the retired /80 scorer.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from score_supplements_v4 import SCORING_ENGINE_VERSION, score_product_v4
from scoring_input_contract import get_scoring_ingredients, scoring_input_scope
from supplement_taxonomy import percentile_label_for


SCORED_ARTIFACT_SCHEMA_VERSION = "4.0.0"
LOW_COVERAGE_TRUST_FLOOR = 0.3


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _display_score(value: Any, status: Any) -> str:
    if status != "scored":
        return "N/A"
    try:
        return f"{round(float(value))}/100"
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
    safety_gate = _safe_dict(breakdown.get("safety_gate"))
    completeness_gate = _safe_dict(breakdown.get("completeness_gate"))
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
    quality_score = v4.get("quality_score_v4_100")
    verdict = _public_verdict(v4, mapped_coverage)
    safety_verdict = str(safety_gate.get("verdict") or "SAFE").upper()
    blocking_reason = safety_gate.get("blocking_reason")
    safety_signals = list(safety_gate.get("safety_signals") or [])
    if verdict == "CAUTION" and mapped_coverage < LOW_COVERAGE_TRUST_FLOOR:
        safety_signals = list(dict.fromkeys(safety_signals + ["low_mapped_coverage"]))

    taxonomy = dict(_safe_dict(enriched_product.get("supplement_taxonomy")))
    percentile_category = taxonomy.get("percentile_category")
    strict_contract = dict(diagnostics["strict_scoring_contract"])
    scored_at = datetime.now(timezone.utc).isoformat()
    config_fingerprint = _config_fingerprint(provenance)

    artifact: Dict[str, Any] = {
        "dsld_id": enriched_product.get("dsld_id"),
        "product_name": enriched_product.get("product_name"),
        "brand_name": enriched_product.get("brand_name") or enriched_product.get("brandName"),
        "evaluation_stage": "scored_v4",
        "output_schema_version": SCORED_ARTIFACT_SCHEMA_VERSION,
        "score_basis": "v4_six_pillar",
        "scoring_status": status,
        "not_scorable_reason": (
            completeness_gate.get("reason") if status == "not_scored" else None
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
        "mapped_coverage_applicable": scoring_input.mapped_coverage_applicable,
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
        "safety_signal_reason": safety_signals[0] if safety_signals else None,
        "flags": safety_signals,
        "badges": [],
        "quality_score_v4_100": quality_score,
        "quality_score_status": status,
        "quality_tier": v4.get("quality_tier"),
        "quality_score_suppressed_reason": v4.get("quality_score_suppressed_reason"),
        "raw_score_v4_100": v4.get("raw_score_v4_100"),
        "quality_pillars_v4": v4.get("quality_pillars_v4"),
        "score_100_equivalent": quality_score,
        "display_100": _display_score(quality_score, status),
        "grade": v4.get("quality_tier"),
        "scoring_metadata": {
            "scoring_version": provenance.get("scoring_engine_version"),
            "output_schema_version": SCORED_ARTIFACT_SCHEMA_VERSION,
            "scored_date": scored_at,
            "scoring_status": status,
            "score_basis": "v4_six_pillar",
            "scoring_ingredients_source": scoring_input.source,
            "strict_scoring_contract": strict_contract,
            "mapped_coverage": round(mapped_coverage, 4),
            "mapped_coverage_applicable": scoring_input.mapped_coverage_applicable,
            "unmapped_actives_total": scoring_input.unmapped_count,
            "verdict": verdict,
            "blocking_reason": blocking_reason,
        },
        "_score_model_version": "v4",
        "_v4_quality_score_100": quality_score,
        "_v4_quality_status": status,
        "_v4_quality_tier": v4.get("quality_tier"),
        "_v4_quality_score_cap": v4.get("quality_score_cap_v4"),
        "_v4_suppressed_reason": v4.get("quality_score_suppressed_reason"),
        "_v4_raw_score_100": v4.get("raw_score_v4_100"),
        "_v4_module": v4.get("v4_module"),
        "_v4_module_breakdown": module_breakdown,
        "_v4_inactive_penalty_details": _inactive_penalty_details(
            module_breakdown
        ),
        "_v4_confidence": v4.get("v4_confidence"),
        "_v4_confidence_detail": breakdown.get("confidence"),
        "_v4_quality_version": v4.get("quality_score_version"),
        "_v4_pillars": v4.get("quality_pillars_v4"),
        "_v4_clean_label_flags": v4.get("clean_label_flags_v4"),
        "_v4_safety_gate": safety_gate,
        "_v4_safety_signal_reason": safety_signals[0] if safety_signals else None,
        "_v4_completeness_gate": completeness_gate,
        "_v4_provenance": provenance,
        "_v4_scoring_engine_version": provenance.get("scoring_engine_version"),
        "_v4_classification_schema_version": provenance.get("classification_schema_version"),
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


def suppress_scored_artifact_for_hard_block(
    artifact: Dict[str, Any], reason: str
) -> Dict[str, Any]:
    """Return a hard-blocked copy of a v4 Stage-3 artifact.

    Final export has a small set of broader regulatory checks than the scoring
    modules. When one fires, every public and reserved score surface must agree
    that the score is safety-suppressed. Raw score and pillar diagnostics remain
    available as an audit trail; they are never consumer-ranking fields.
    """
    if not isinstance(artifact, dict):
        raise TypeError("scored artifact must be an object")

    blocked = dict(artifact)
    blocked.update({
        "verdict": "BLOCKED",
        "safety_verdict": "BLOCKED",
        "quality_score_v4_100": None,
        "quality_score_status": "suppressed_safety",
        "quality_tier": None,
        "quality_score_suppressed_reason": (
            blocked.get("quality_score_suppressed_reason") or reason
        ),
        "score_100_equivalent": None,
        "display_100": "N/A",
        "grade": None,
        "scoring_status": "suppressed_safety",
        "blocking_reason": blocked.get("blocking_reason") or reason,
        "safety_signal_reason": blocked.get("safety_signal_reason") or reason,
        "_v4_quality_score_100": None,
        "_v4_quality_status": "suppressed_safety",
        "_v4_quality_tier": None,
        "_v4_suppressed_reason": blocked.get("_v4_suppressed_reason") or reason,
        "_v4_safety_signal_reason": (
            blocked.get("_v4_safety_signal_reason") or reason
        ),
    })

    metadata = dict(_safe_dict(blocked.get("scoring_metadata")))
    metadata.update({
        "scoring_status": "suppressed_safety",
        "verdict": "BLOCKED",
        "blocking_reason": blocked["blocking_reason"],
    })
    blocked["scoring_metadata"] = metadata

    safety_gate = dict(_safe_dict(blocked.get("_v4_safety_gate")))
    signals = list(safety_gate.get("safety_signals") or [])
    if reason not in signals:
        signals.append(reason)
    safety_gate.update({
        "verdict": "BLOCKED",
        "blocking_reason": safety_gate.get("blocking_reason") or reason,
        "safety_signals": signals,
    })
    blocked["_v4_safety_gate"] = safety_gate
    return blocked
