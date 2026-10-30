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
from typing import Any, Dict, Optional

from score_supplements_v4 import score_product_v4
from scoring_input_contract import (
    build_scoring_classification,
    get_scoring_ingredients,
    score_eligible_identity_view,
    scoring_input_scope,
)
from scoring_v4.gate_safety import safety_resolvers_failed, stated_safety_signal
from supplement_taxonomy import percentile_label_for


SCORED_ARTIFACT_SCHEMA_VERSION = "4.4.0"
#: Compatibility disposition precedence, including retired POOR for reading
#: existing catalogs. New artifacts never emit POOR; quality_tier owns quality.
#: Consumer safety is exclusively product_safety_status, not this legacy field.
PUBLIC_VERDICT_PRECEDENCE = ("BLOCKED", "UNSAFE", "NOT_SCORED", "CAUTION", "POOR", "SAFE")


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


def _public_verdict(v4: Dict[str, Any]) -> str:
    """Resolve legacy verdict precedence without treating coverage as risk."""
    status = str(v4.get("quality_score_status") or "")
    verdict = str(v4.get("v4_verdict") or "").upper()
    if status == "suppressed_safety":
        return verdict if verdict in {"BLOCKED", "UNSAFE"} else "BLOCKED"
    if status == "not_scored":
        return "NOT_SCORED"
    if status != "scored":
        return "NOT_SCORED"
    if verdict in {"BLOCKED", "UNSAFE", "CAUTION"}:
        return verdict
    return "SAFE"


def _product_safety_status(
    safety_gate: Dict[str, Any],
    *,
    was_assessed: bool,
) -> str:
    """Project only catalog safety-gate policy into the consumer safety state.

    Legacy verdict also carries compatibility and quality history, so it must
    never be the source for this field.
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
    if safety_resolvers_failed(safety_gate.get("ingredient_assessment_errors")):
        # No hard verdict, and a safety resolver never checked the rows.
        return "not_assessed"
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


#: Routes whose Dose assesses vitamin and mineral adequacy.
_NUTRIENT_DOSE_ROUTES = frozenset({"generic", "multi_or_prenatal", "b_complex"})
#: Generic Dose methods that read vitamin/mineral amounts (the botanical,
#: collagen, sleep and joint profiles never do).
_GENERIC_NUTRIENT_DOSE_METHODS = frozenset({
    "source_qualified_contribution_and_completed_neutral",
    "immune_support_daily_dose_v1",
})
#: Adequacy statuses recorded when a printed nutrient amount could not be read.
#: An unstated vitamin form is the label's limitation (its upper-limit risk is
#: dose-safety's unresolved state), so it is not listed here.
_UNREAD_NUTRIENT_AMOUNT_STATUSES = frozenset({
    "skipped_unit_unrecognized",
    "skipped_amount_not_declared",
})


def unfinished_source_assessment(enriched_product: Dict[str, Any],
                                 module_breakdown: Dict[str, Any]) -> Optional[str]:
    """Name PharmaGuide's own unfinished work, never a label limitation (V4.1 Step 4).

    A hidden or missing amount is the label's limitation and stays scored. These
    are ours: a botanical whose benchmark identity we could not resolve, a
    printed nutrient amount or unit we could not read, and a printed sugars
    line whose amount we could not read.
    """
    dose_meta = _safe_dict(_safe_dict(_safe_dict(module_breakdown.get("dimensions")).get("dose")).get("metadata"))
    if (dose_meta.get("assessment_status") == "incomplete"
            and dose_meta.get("reason_code") == "unresolved_source_quantity"):
        return "dose_amount_unread"
    assessments = [(dose_meta.get("botanical_dose_band"),
                    _safe_dict(dose_meta.get("botanical_dose")))] + [
        (_safe_dict(item).get("band"), _safe_dict(_safe_dict(item).get("metadata")))
        for item in dose_meta.get("specialized_purpose_assessments") or []
    ]
    if any(item.get("benchmark") == "unresolved" and not (
            band in {"blend_total_only", "primary_no_dose"}
            and item.get("assessment_status") == "complete"
            and item.get("reason_code") == "amount_not_declared")
           for band, item in assessments):
        return "dose_benchmark_identity_unresolved"
    # A printed botanical/collagen amount the exposure owner could not read.
    bands = {dose_meta.get("botanical_dose_band"), dose_meta.get("collagen_dose_band")} | {
        _safe_dict(item).get("band") for item in dose_meta.get("specialized_purpose_assessments") or []
    }
    if "amount_not_assessable" in bands:
        return "dose_amount_unread"
    # Only a nutrient the route's Dose benchmarks (the adequacy owner found its
    # RDA/UL reference record; its RDA/AI is never computed for an unread
    # amount), and only when the owner recorded a printed number it could not
    # read: an incidental vitamin on a protein or fiber label does not hold the
    # tier, and an amount the label never printed is the label's limitation.
    module = module_breakdown.get("module")
    if module in _NUTRIENT_DOSE_ROUTES and (
        module != "generic" or dose_meta.get("method") in _GENERIC_NUTRIENT_DOSE_METHODS
    ):
        for row in _safe_dict(enriched_product.get("rda_ul_data")).get("adequacy_results") or []:
            if not isinstance(row, dict) or row.get("ul_status") not in _UNREAD_NUTRIENT_AMOUNT_STATUSES:
                continue
            printed = row.get("original_quantity")
            if (row.get("data_by_group") and isinstance(printed, (int, float))
                    and not isinstance(printed, bool) and printed > 0):
                return "nutrient_amount_unread"
    # The enricher owns the sugar reading: a printed sugars line it classified
    # but could not read as an exact mass keeps its level with no amount.
    sugar = _safe_dict(_safe_dict(enriched_product.get("dietary_sensitivity_data")).get("sugar"))
    if sugar.get("contains_sugar") and sugar.get("level") and sugar.get("amount_g") is None:
        return "sugar_amount_unread"
    return None


def _quality_assessment_status(
    quality_score_status: str,
    dose_safety: Dict[str, Any],
    pillars: Dict[str, Any] | None = None,
    unfinished: Optional[str] = None,
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
    if unfinished and quality_score_status == "scored":
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
        #       retain partial assessment state. Catalog eligibility separately
        #       requires usable source-label identity and null quality fields.
        return "partial"
    return "failed"


def _held_assessment_label(product: Dict[str, Any], release: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Match an approved unavailable assessment to its intact source edition.

    With release facts, this qualifies score unavailability, never completion.
    Without them, consumers may only qualify the source-bound precaution copy;
    they cannot infer that a release or safety assessment succeeded.
    """
    from label_record_contract import build_label_record_contract
    from scoring_input_contract import _source_tree_rows
    from scoring_v4.quality_score_config import config

    if release is not None and (release.get("is_complete") is not False
            or not isinstance(release.get("blockers"), list)
            or not release["blockers"]):
        return {}
    entries = _safe_dict(_safe_dict(config().get("suppression")).get("held_assessment_labels"))
    entry = _safe_dict(entries.get(str(product.get("dsld_id") or "")))
    if not entry or not all(entry.get(key) for key in (
            "reviewer", "review_date", "review_scope", "source_url", "source_rows")):
        return {}
    if release is not None and set(release.get("blockers") or []) != set(entry.get("blockers") or []):
        return {}
    if (release is not None and "unfinished_source_assessment" in entry
            and release.get("unfinished_source_assessment") != entry["unfinished_source_assessment"]):
        return {}
    try:
        label = build_label_record_contract(product, product.get("display_ingredients"))
    except ValueError:
        return {}
    if (label.get("source_record_id") != str(product.get("dsld_id") or "")
            or label.get("source_name") != entry.get("source_name")
            or not label.get("formula_fingerprint")
            or label["formula_fingerprint"] != entry.get("formula_fingerprint")):
        return {}
    # Bind original physical assertions too: display identity alone cannot
    # establish an unchanged species, tissue, assay or preparation edition.
    fields = ("raw_source_path", "raw_source_text", "quantity", "unit", "notes",
              "forms", "plantPart", "genus", "species")
    return entry if [{key: row.get(key) for key in fields} for row in _source_tree_rows(product)] == entry["source_rows"] else {}


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
    formulation = _safe_dict(_safe_dict(_safe_dict(module_breakdown).get("dimensions")).get("formulation"))
    delivery_data = _safe_dict(_safe_dict(formulation.get("metadata")).get("delivery_data"))

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
    unfinished = unfinished_source_assessment(enriched_product, _safe_dict(module_breakdown))
    from assessment_readiness import evaluate_release_assessment
    assessment_readiness = {**assessment_readiness, "release_assessment": evaluate_release_assessment(
        enriched_product, assessment_readiness, _safe_dict(module_breakdown),
        unfinished_source=unfinished,
    )}
    if (status == "scored" and safety_gate.get("verdict") not in {"BLOCKED", "UNSAFE"}
            and safety_gate.get("ingredient_assessment_complete") is True
            and not safety_resolvers_failed(safety_gate.get("ingredient_assessment_errors"))
            and safety_gate.get("quarantine_required") is not True
            and _held_assessment_label(enriched_product, assessment_readiness["release_assessment"])):
        # Reuse the public score owner's existing unavailable branch rather
        # than manufacturing a second set of score/mirror/tier nulling rules.
        from scoring_v4.quality_score import assemble_quality_score
        v4 = assemble_quality_score({**v4, "raw_score_v4_100": None,
                                    "v4_verdict": "NOT_SCORED"})
        status = v4["quality_score_status"]
        score_unavailable_reason = "release_assessment_incomplete"
    # The release owner distinguishes a completed negative answer from an
    # unresolved source review. A provisional calculation must render the
    # same completeness conclusion without recomputing that policy here.
    release_complete = assessment_readiness["release_assessment"]["is_complete"]
    quality_assessment_status = _quality_assessment_status(
        status, dose_safety, v4.get("quality_pillars_v4"),
        unfinished or (None if release_complete else "release_assessment_incomplete"),
    )
    quality_score = v4.get("quality_score_v4_100")
    verdict = _public_verdict(v4)
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

    taxonomy = dict(_safe_dict(enriched_product.get("supplement_taxonomy")))
    percentile_category = taxonomy.get("percentile_category")
    strict_contract = dict(diagnostics["strict_scoring_contract"])
    scored_at = datetime.now(timezone.utc).isoformat()
    config_fingerprint = _config_fingerprint(provenance)
    classification = build_scoring_classification(enriched_product)
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
        "delivery_data": delivery_data or {"matched": False, "systems": [], "highest_tier": None},
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
        "safety_signal_reason": decision_reason or stated_safety_signal(safety_signals),
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
    scoring_product = score_eligible_identity_view(enriched_product)
    with scoring_input_scope(scoring_product):
        return assemble_scored_artifact(
            enriched_product,
            score_product_v4(scoring_product),
        )


