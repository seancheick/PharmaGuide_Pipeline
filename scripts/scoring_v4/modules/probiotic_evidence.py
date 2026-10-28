"""Probiotic Evidence: certainty /10, applicability /6, confirmation /4.

The existing Dose owner assesses amounts. Exact-formula research owns its
intervention; unrelated species or member studies cannot replace it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from scoring_v4.modules.generic_evidence import (
    EFFECT_DIRECTION_MULTIPLIERS as GENERIC_EFFECT_MULTIPLIERS,
    EVIDENCE_LEVEL_MULTIPLIERS,
    evidence_completeness_gap,
    resolved_clinical_matches,
)
from probiotic_measurements import context_accepted_for_scoring, context_review_finished
from studied_formulas import (assess_probiotic_evidence,
                             assess_studied_formula_identity,
                             assess_probiotic_component_disposition,
                             independent_clinical_strains, reviewed_strains_without_qualifying_evidence,
                             strain_assessments_for_match,
                             valid_native_study_context, reviewed_native_context_present)


PHASE_MARKER = "P2.3_probiotic_evidence"
from scoring_v4.quality_score_config import block as _cfg_block

_EM = _cfg_block("evidence_magnitudes", "probiotic")["probiotic"]


CAP_EVIDENCE = _EM["cap_evidence"]

from clinical_applicability import NON_EFFICACY_OUTCOME_ROLES as _NON_EFFICACY_OUTCOME_ROLES
from evidence_resolver import evidence_indication_categories as _categories_from_text


BROAD_PROBIOTIC_CATEGORIES = {"digestive", "immune"}
PARTIAL_RELEVANCE_PAIRS = {
    ("prenatal", "infant"),
    ("prenatal", "immune"),
    ("women", "prenatal"),
    ("digestive", "immune"),
}


def score_evidence(product: Any) -> Dict[str, Any]:
    """Assess research certainty, product applicability and independent confirmation.

    Label amounts never award or veto Evidence. Dose consumes the same reviewed
    trial comparisons from assess_probiotic_evidence, including unknown amounts.
    """
    product = product if isinstance(product, dict) else {}
    assessment = assess_probiotic_evidence(product)
    formula = assess_studied_formula_identity(product)
    matches, _ = resolved_clinical_matches(product, assess_amount=False)
    accepted = [m for m in matches if not _is_strain_match(m)
                or strain_assessments_for_match(m, assessment)]
    owned = [m for m in accepted if _is_probiotic_owned_match(m, formula)]
    if formula.get("status") == "assessed_studied_formula":
        owned = [m for m in owned if m.get("id") == formula.get("evidence_id")]
    relevance = _claim_alignment(product, {**assessment, "formula_assessment": formula})
    family_assessment = (
        {**assessment, "strain_assessments": []}
        if formula.get("status") == "assessed_studied_formula" else assessment
    )
    family = _strongest_single_family_certainty(
        probiotic_owned=owned, assessment=family_assessment,
        relevance=relevance, settings=_EM, formula=formula,
    )
    alignment = _applicability_weight(family, formula, relevance)
    applicability = alignment * family["identity_weight"] if family["certainty"] > 0 else 0.0
    consistency = _independent_consistency(family_assessment)
    # Certainty and confirmation describe research that must first apply to this
    # product; without applicability they earn nothing (V4.1, October 15, 2026).
    # The result state still describes the research found, before that gate.
    research = {
        "evidence_family_certainty": round(_EM["certainty_cap"] * family["certainty"], 4),
        "product_applicability": round(_EM["applicability_cap"] * applicability, 4),
        "independent_replication_consistency": round(_EM["replication_cap"] * consistency["credit"], 4),
    }
    research_score = min(CAP_EVIDENCE, sum(research.values()))
    applies = research["product_applicability"] > 0
    components = {key: value if applies or key == "product_applicability" else 0.0
                  for key, value in research.items()}
    score = min(CAP_EVIDENCE, sum(components.values()))
    completeness_gap = evidence_completeness_gap(product)
    strain_review_open = formula.get("status") != "assessed_studied_formula" and (
        assessment["native_context_review"]["status"] == "pending_clinical_review"
        or any(row["status"] == "strain_identity_or_review_unresolved"
               for row in assessment["strain_assessments"]))
    eligible = _eligible_native_contexts(family_assessment)
    # The shared assessment inventories research, including legacy reference
    # citations. Report scoring provenance from the family that actually won
    # this pillar; inventory sources must not masquerade as awarded evidence.
    for strain in assessment["strain_assessments"]:
        strain["scoring_source_pmids"] = sorted({
            pmid for clinical_id, context in eligible
            if family["source"] == "native_context" and score > 0
            and clinical_id == strain.get("clinical_id")
            and (context.get("trial_family") or context.get("context_id")) == family["family"]
            for pmid in context.get("source_pmids") or []
        })
    contributing_contexts = []
    contributing_records = []
    if score > 0:
        if family["source"] == "native_context":
            contributing_contexts.append(family["context"])
        elif family["source"] == "registry":
            from clinical_applicability import assess_clinical_applicability, assess_clinical_source_review
            for entry in owned:
                if entry.get("id") == family["family"]:
                    decision = (formula if formula.get("status") == "assessed_studied_formula"
                                else assess_clinical_applicability(product, entry, assess_amount=False))
                    contributing_records.append({"id": entry.get("id"), **decision,
                        "source_review": assess_clinical_source_review(entry),
                        "scope_qualification_complete": bool(decision.get("studied_population")
                            and decision.get("supported_outcomes"))})
                    break
        if components["independent_replication_consistency"] > 0:
            selected = next(row for row in consistency["conditions"] if row["credit"] == consistency["credit"])
            contributing_contexts.extend(context for _, context in eligible
                if context.get("condition") == selected["condition"]
                and (context.get("trial_family") or context.get("context_id")) in selected["families"])
    contributing_contexts = list({context["context_id"]: context for context in contributing_contexts}.values())
    directions = [outcome.get("direction") for _, context in eligible
                  for outcome in _qualifying_outcomes(context)]
    directions += [_norm_text(row.get("effect_direction")) for row in owned]
    if completeness_gap:
        state = completeness_gap
    elif strain_review_open:
        state = "native_research_review_incomplete"
    elif research_score == 0 and "negative" in directions:
        state = "evaluated_unfavorable"
    elif research_score == 0 and directions and all(d == "null" for d in directions):
        state = "evaluated_null"
    elif components["product_applicability"] > 0:
        state = "evaluated_applicable"
    elif score == 0 and reviewed_strains_without_qualifying_evidence(assessment["strain_assessments"]):
        state = "no_qualifying_human_evidence"
    elif research_score > 0 or any(
            reviewed_native_context_present(row)
            for row in assessment["strain_assessments"]):
        state = "research_present_applicability_unestablished"
    elif any(not _human_research_reviewed({"clinical_id": row.get("clinical_id")}, assessment)
             for row in assessment["strain_assessments"]
             if row.get("research_accepted") and row.get("human_evidence") is not True):
        state = "human_clinical_evidence_unestablished"
    elif assessment["strain_assessments"]:
        # A zero-credit reviewed identity still needs applicable primary
        # research. A matching amount cannot establish Evidence applicability.
        state = "applicability_unestablished"
    else:
        state = assess_probiotic_component_disposition(product).get("disposition_state") or "applicability_unestablished"
    return {
        "score": round(score, 4), "max": CAP_EVIDENCE, "components": components,
        "penalties": {}, "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER, "evidence_assessment": assessment,
            "contributing_native_contexts": contributing_contexts,
            "contributing_record_assessments": contributing_records,
            "evidence_result_state": state, "claim_alignment": relevance,
            "studied_formula_assessment": formula,
            "credit_owner": "none" if score <= 0 else (
                "studied_formula" if formula.get("status") == "assessed_studied_formula" else "strain"),
            "strain_points": components["evidence_family_certainty"],
            "companion_points": 0.0, "final_points": round(score, 4),
            "uncredited_strain_match_ids": [m.get("id") for m in matches if m not in accepted],
            "clinical_strain_count": len(_clinical_strains(product)),
            "indication_relevance_level": relevance["level"],
            "product_positioning_categories": sorted(relevance["product_categories"]),
            "strain_indication_categories": sorted(relevance["strain_categories"]),
            "matched_relevance_categories": sorted(relevance["matched_categories"]),
            "relevance_reason": relevance["reason"],
            "notes": (f"Strongest family: {family['family']}; source: {family['source']}; "
                      f"recorded design: {family['design']}; recorded direction: {family['direction']}. "
                      "Other reviewed findings remain scoped to their own condition and population."),
        },
    }


def _applicability_weight(family: dict, formula: dict, relevance: dict) -> float:
    """Product applicability from the shared scientific decision, never from marketing.

    Sean, October 28, 2026 (PR #280): an aligned claim and no claim earn the
    same points for the same eligible research. A studied formula, an approved
    native context or a registry record the shared applicability owner accepted
    applies in full. A legacy record whose eligibility was never reviewed keeps
    the claim-independent broad weight; an unrelated positioning still earns
    nothing. Claim alignment stays explanation metadata.
    """
    weights = _EM["alignment_weights"]
    if formula.get("status") == "assessed_studied_formula" or family.get("source") == "native_context":
        return weights["direct"]
    if (family.get("source") == "registry"
            and (family.get("decision") or {}).get("status") == "applicable"):
        return weights["direct"]
    return 0.0 if relevance["level"] == "none" else weights["broad"]


def _strongest_single_family_certainty(
    *, probiotic_owned: list[dict], assessment: dict, relevance: dict, settings: dict,
    formula: dict,
) -> dict:
    """Return one winning family and its own identity, without depth/replication."""
    families = [{
        "certainty": _single_generic_family_certainty(row, settings),
        "identity_weight": (
            1.0 if formula.get("status") == "assessed_studied_formula"
            and row.get("id") == formula.get("evidence_id")
            else float(settings.get("generic_identity_weight") or 0.0)
        ),
        "family": row.get("id"), "source": "registry",
        "design": row.get("study_type"), "direction": row.get("effect_direction"),
        "decision": row.get("applicability_assessment"),
    } for row in probiotic_owned]
    families += [{
        "certainty": _single_native_family_certainty(context, settings),
        "identity_weight": 1.0,
        "family": context.get("trial_family") or context.get("context_id"),
        "source": "native_context", "design": context.get("study_design"),
        "context": context,
        "direction": sorted({o.get("direction") for o in _qualifying_outcomes(context)}),
    } for _, context in _eligible_native_contexts(assessment)]
    return max(families, key=lambda row: (row["certainty"], row["identity_weight"]), default={
        "certainty": 0.0, "identity_weight": 0.0, "family": None,
        "source": None, "design": None, "direction": None,
    })


def _single_generic_family_certainty(entry: dict, settings: dict | None = None) -> float:
    """Adapt reviewed registry facts to the same family scale as native contexts.

    Evidence level gates human research; identity strength belongs exclusively
    to product applicability. A clinical-strain summary without a reported
    design retains the existing conservative design-only value, never an RCT.
    """
    if settings is None:
        settings = _EM
    level = _norm_text(entry.get("evidence_level")).replace(" ", "_")
    if level not in EVIDENCE_LEVEL_MULTIPLIERS or level in {"preclinical", "reference"}:
        return 0.0
    return _single_family_certainty(
        design=entry.get("study_type"), effect=entry.get("effect_direction") or "unreported", settings=settings,
    )


def _single_native_family_certainty(context: dict, settings: dict) -> float:
    directions = {outcome.get("direction") for outcome in _qualifying_outcomes(context)}
    if "positive" not in directions:
        return 0.0
    result = _single_family_certainty(
        design=context.get("study_design"),
        effect=context.get("effect_direction"), settings=settings,
    )
    if directions != {"positive"}:
        result = min(result, _single_family_certainty(
            design=context.get("study_design"), effect="mixed", settings=settings,
        ))
    return result


def _single_family_certainty(*, design: str | None, effect: str | None, settings: dict) -> float:
    """One design/effect computation, independent of registry representation."""
    design = _norm_text(design).replace(" ", "_")
    design = {
        "rct_single": "rct", "rct_multiple": "rct",
        "systematic_review_meta": "meta_analysis",
    }.get(design, design)
    weights = settings.get("single_family_design_weights") or {}
    if design == "clinical_strain":
        # This record does not assert an RCT. Preserve its existing design
        # strength without the old second identity discount.
        design_weight = float(settings["unspecified_human_design_weight"])
    else:
        design_weight = float(weights.get(design, 0.0))
    # A native primary outcome's positive direction does not assert an effect
    # strength. Keep its existing unmodified design credit when no graded fact
    # was recorded; do not derive a strength from aggregate trial counts.
    effect_weight = (
        GENERIC_EFFECT_MULTIPLIERS["positive_strong"] if effect is None
        else GENERIC_EFFECT_MULTIPLIERS.get(_norm_text(effect).replace(" ", "_"), 0.0)
    )
    return min(1.0, max(0.0, design_weight * effect_weight))


def _independent_consistency(assessment: dict) -> dict:
    """Grade confirmation and disclose applicable contradictory families."""
    return _consistency_from_contexts(_eligible_native_contexts(assessment))


def _consistency_from_contexts(contexts: list[tuple[str, dict]]) -> dict:
    """Summarize already-eligible contexts without re-owning applicability.

    Two consistent RCT families earn half credit. Three or more earn the
    maximum. Pooled records receive no extra credit until the registry links
    their underlying independent families. Any applicable null, negative, or
    mixed family for the same condition suppresses consistency credit.
    """
    by_condition: dict[str, dict[str, dict]] = {}
    for clinical_id, context in contexts:
        condition = str(context.get("condition") or "").strip()
        family = str(context.get("trial_family") or context.get("context_id") or "").strip()
        if not condition or not family:
            continue
        directions = {
            outcome.get("direction") for outcome in _qualifying_outcomes(context)
        }
        if directions == {"positive"}:
            direction = "positive"
        elif directions == {"null"}:
            direction = "null"
        elif directions == {"negative"}:
            direction = "negative"
        else:
            direction = "mixed"
        family_row = by_condition.setdefault(condition, {}).setdefault(family, {
            "clinical_ids": set(), "directions": set(), "designs": set(),
        })
        family_row["clinical_ids"].add(clinical_id)
        family_row["directions"].add(direction)
        family_row["designs"].add(str(context.get("study_design") or "unreported"))

    condition_rows = []
    best_credit = 0.0
    for condition, families in sorted(by_condition.items()):
        normalized = {}
        for family, row in sorted(families.items()):
            direction = (
                next(iter(row["directions"]))
                if len(row["directions"]) == 1 else "mixed"
            )
            normalized[family] = {
                "clinical_ids": sorted(row["clinical_ids"]),
                "direction": direction,
                "designs": sorted(row["designs"]),
            }
        positive_rcts = [
            family for family, row in normalized.items()
            if row["direction"] == "positive"
            and set(row["designs"]).intersection({"rct", "crossover_rct", "cluster_rct"})
        ]
        contradictory = [
            family for family, row in normalized.items()
            if row["direction"] in {"null", "negative", "mixed"}
        ]
        pooled = [
            family for family, row in normalized.items()
            if set(row["designs"]).intersection({"meta_analysis", "systematic_review", "guideline"})
        ]
        if contradictory or pooled:
            credit = 0.0
        elif len(positive_rcts) >= 3:
            credit = 1.0
        elif len(positive_rcts) == 2:
            credit = 0.5
        else:
            credit = 0.0
        best_credit = max(best_credit, credit)
        condition_rows.append({
            "condition": condition,
            "families": normalized,
            "positive_rct_family_count": len(positive_rcts),
            "contradictory_family_ids": contradictory,
            "pooled_family_ids": pooled,
            "credit": credit,
        })
    return {
        "credit": best_credit,
        "conditions": condition_rows,
        "has_material_conflict": any(
            row["positive_rct_family_count"] > 0
            and row["contradictory_family_ids"]
            for row in condition_rows
        ),
    }




def _qualifying_outcomes(context: dict) -> list[dict]:
    from clinical_applicability import qualifying_purpose_outcomes
    outcomes, _ = qualifying_purpose_outcomes(context, include_nonpositive=True)
    return [outcome for outcome in outcomes if outcome.get("kind") == "patient_important"]


def _eligible_native_contexts(assessment: dict) -> list[tuple[str, dict]]:
    """Return valid, exact-strain contexts applicable to this product's purpose."""
    result = []
    for strain in assessment.get("strain_assessments") or []:
        if strain.get("research_accepted") is False or strain.get("status") in {
            "strain_context_mismatch", "strain_context_unresolved", "strain_identity_mismatch",
            "strain_identity_or_review_unresolved", "strain_reference_unreviewed",
        }:
            continue
        clinical_id = str(strain.get("clinical_id") or "").strip()
        for context in strain.get("study_contexts") or []:
            if (not clinical_id
                    or context.get("identity_scope") != "exact_strain"
                    or not context_accepted_for_scoring(context)
                    or not valid_native_study_context(context, clinical_id)
                    or not _qualifying_outcomes(context)):
                continue
            # The shared applicability owner decided claim and population on
            # this label: no claim is required, an unrelated claim or a
            # special population without targeting keeps the context out.
            if not _native_context_applies(context):
                continue
            result.append((clinical_id, context))
    return result


def _native_context_applies(context: dict) -> bool:
    return (context.get("claimed_purpose_assessment", {}).get("status") == "applicable"
            and context.get("population_applicability") == "eligible")


def _human_research_reviewed(uncredited_row: Dict[str, Any], assessment: Dict[str, Any]) -> bool:
    """True when the strain has recorded study contexts and every one is reviewed."""
    contexts = [
        context
        for strain in assessment["strain_assessments"]
        if strain.get("clinical_id") == uncredited_row.get("clinical_id")
        for context in strain.get("study_contexts") or []
        if context.get("status") == "source_context_recorded"
    ]
    return bool(contexts) and all(context_review_finished(c) for c in contexts)


def _claim_alignment(product: Dict[str, Any], assessment: Dict[str, Any]) -> Dict[str, Any]:
    from clinical_applicability import native_product_positioning_categories
    product_categories = native_product_positioning_categories(product)
    strain_categories = _strain_indication_categories(assessment)
    matched = product_categories & strain_categories
    partial = {
        b
        for a, b in PARTIAL_RELEVANCE_PAIRS
        if (a in product_categories and b in strain_categories)
        or (b in product_categories and a in strain_categories)
    }
    broad = strain_categories & BROAD_PROBIOTIC_CATEGORIES
    if matched:
        level, reason = "direct", "direct_category_overlap"
    elif partial:
        level, reason, matched = "partial", "related_category_overlap", partial
    elif not product_categories and broad:
        level, reason, matched = "broad", "generic_probiotic_positioning", broad
    elif not product_categories and not strain_categories:
        level, reason = "not_evaluable", "missing_positioning_or_indication_data"
    else:
        level, reason = "none", "no_relevance_overlap"
    return {
        "level": level,
        "product_categories": sorted(product_categories),
        "strain_categories": sorted(strain_categories),
        "matched_categories": sorted(matched),
        "reason": reason,
    }


def _is_probiotic_owned_match(match: dict, formula: dict) -> bool:
    """A match that speaks for the probiotic itself: strain evidence, the
    studied-formula record, or research on a probiotic organism named by the
    one identity owner (probiotic_measurements). Anything else — vitamins,
    botanicals, fiber — is a companion."""
    from probiotic_measurements import has_probiotic_identity_text

    if _is_strain_match(match):
        return True
    if formula.get("evidence_id") and match.get("id") == formula.get("evidence_id"):
        return True
    return has_probiotic_identity_text(
        " ".join(str(match.get(field) or "") for field in ("ingredient", "standard_name"))
    )


def _is_strain_match(match: dict) -> bool:
    return (match.get("study_type") == "clinical_strain"
            or str(match.get("evidence_level", "")).replace("_", "-") == "strain-clinical")


def _strain_indication_categories(assessment: Dict[str, Any]) -> Set[str]:
    """Use current registry copy from the same assessment that owns credit."""
    categories: Set[str] = set()
    for strain in assessment["strain_assessments"]:
        if not strain["research_accepted"]:
            continue
        indication_categories = _categories_from_text(str(strain.get("indication_primary") or ""))
        if not indication_categories:
            # Context-owned research need not carry a legacy summary indication.
            # Reuse reviewed primary-outcome facts; pending and combination
            # contexts cannot supply the missing purpose.
            for context in strain.get("study_contexts") or []:
                if (context.get("identity_scope") == "exact_strain"
                        and context_accepted_for_scoring(context)
                        and valid_native_study_context(context, strain.get("clinical_id"))
                        and _native_context_applies(context)):
                    text = " ".join([str(context.get("condition") or ""),
                        *(str(outcome.get("name") or "") for outcome in _qualifying_outcomes(context))])
                    if _qualifying_outcomes(context):
                        indication_categories.update(_categories_from_text(text))
        categories.update(indication_categories)
    formula = assessment["formula_assessment"]
    if formula["status"] == "assessed_studied_formula":
        categories.update(formula["supported_outcomes"])
    return categories


def _clinical_strains(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return independent_clinical_strains(product)


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()
