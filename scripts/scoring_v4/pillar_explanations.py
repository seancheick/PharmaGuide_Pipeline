"""Pipeline-authored pillar explanation facts.

A pure adapter that turns module-breakdown metadata the scorer already computed
into small, versioned "facts" that explain a pillar. It never recomputes a
score and never mutates ``score``/``max``/``reason`` — it only attaches an
optional ``explanation`` block to a pillar. New fact sources are added here,
not in the scorer.

Every fact carries ``audience``: ``"consumer"`` for the one key fact the app
shows under the pillar's one-sentence reason (Sean, 2026-10-20), ``"audit"`` for
detail kept for the dashboard and audits. A pillar has at most one consumer
fact; consumer text names ingredients by display name and carries no points,
policy paragraphs or arithmetic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PILLAR_EXPLANATION_SCHEMA_VERSION = 2

CONSUMER = "consumer"
AUDIT = "audit"

# Internal omega molecular-form codes (omega_formulation._detect_form) -> the
# consumer copy shown on the score card. "undefined" is intentionally absent so
# an undisclosed form emits no fact rather than a guess.
_OMEGA_FORM_COPY = {
    "tg": "Triglyceride",
    "rtg": "Re-esterified triglyceride",
    "pl": "Phospholipid",
    "ee": "Ethyl ester",
}


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_mg_per_day(value: float) -> str:
    return f"{int(round(value))} mg/day"


def _amount(value: float) -> str:
    """Consumer number: thousands separators, no trailing zeros."""
    rounded = round(value, 2)
    if float(rounded).is_integer():
        return f"{int(rounded):,}"
    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def audit_fact(fact_id: str, label: str, value_display: str) -> Dict[str, Any]:
    """A detail fact kept for the dashboard and audits, never shown to users."""
    return {"id": fact_id, "label": label, "value_display": value_display, "audience": AUDIT}


def _nonnegative_int(value: Any) -> Optional[int]:
    if type(value) is not int or value < 0:
        return None
    return value


def _omega_dose_facts(dose_dim: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = dose_dim.get("metadata") if isinstance(dose_dim, dict) else None
    # Dose V4.1: adequacy reads the lowest directed daily use, not the midpoint.
    per_day = _num((metadata or {}).get("per_day_min_mg"))
    if per_day is None or per_day <= 0:
        return []
    return [
        {
            "id": "epa_dha_per_day",
            "label": "EPA + DHA per day (lowest directed use)",
            "value_mg": round(per_day, 1),
            "value_display": _format_mg_per_day(per_day),
        }
    ]


def _omega_formulation_facts(formulation_dim: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = formulation_dim.get("metadata") if isinstance(formulation_dim, dict) else None
    code = str((metadata or {}).get("form_detected") or "").strip().lower()
    display = _OMEGA_FORM_COPY.get(code)
    if not display:
        return []
    return [
        {
            "id": "omega_form",
            "label": "Molecular form",
            "value": code,
            "value_display": display,
        }
    ]


def _proprietary_blend_facts(transparency_dim: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = transparency_dim.get("metadata") if isinstance(transparency_dim, dict) else None
    evidence = metadata.get("B5_blend_evidence") if isinstance(metadata, dict) else None
    if not isinstance(evidence, list) or not evidence:
        return []

    hidden_count = 0
    for entry in evidence:
        if not isinstance(entry, dict):
            return []
        count = _nonnegative_int(entry.get("children_without_amount_count"))
        if count is None:
            return []
        hidden_count += count

    return [
        {
            "id": "proprietary_blend_count",
            "label": "Proprietary blends",
            "value_display": str(len(evidence)),
        },
        {
            "id": "undisclosed_ingredient_amount_count",
            "label": "Ingredient amounts not disclosed",
            "value_display": str(hidden_count),
            # The disclosure gap is the key fact only when an amount is hidden.
            "audience": CONSUMER if hidden_count else AUDIT,
        },
    ]


def _zero_evidence_facts(
    pillar: Dict[str, Any], evidence_dim: Dict[str, Any]
) -> List[Dict[str, Any]]:
    if _num(pillar.get("score")) != 0:
        return []
    # Only a finished review may report "0 records": for an applicability or
    # coverage-gap zero that reads as "no research", which the state denies.
    if pillar.get("display_state") != "assessed":
        return []
    metadata = evidence_dim.get("metadata") if isinstance(evidence_dim, dict) else None
    matched_entries = metadata.get("matched_entries") if isinstance(metadata, dict) else None
    if type(matched_entries) is not int or matched_entries != 0:
        return []
    return [
        {
            "id": "matched_evidence_records",
            "label": "Qualifying evidence matches",
            "value_display": "0 in PharmaGuide's current evidence data",
            "audience": CONSUMER,
        }
    ]


# Fact builders keyed by the pillar assembler that owns them. Adding a new
# fact-bearing pillar is a one-line entry here.
# --- Dose receipt (Dose V4.1 section 4) -------------------------------------
# Built only from what the Dose owners recorded; raw credits are converted to
# the public scale by the pillar's own reference, never re-benchmarked.

_AGGREGATION_COPY = {
    "declared_purpose_equal_weight": "Each declared purpose ingredient counts equally; adequacy is their average.",
    "assessed_nutrient_average": "Each assessed nutrient counts equally; adequacy is their average.",
    "co_primary_average": "The main sports actives count equally; adequacy is their average.",
    "single_primary": "Adequacy is the main sports active's assessment.",
    "strongest_dosed_anchor": "Adequacy is the best-dosed recognized sports active's assessment.",
    "strain_average_with_neutral_states": ("Each strain counts equally; a strain without an assessable amount "
                                           "or benchmark takes the neutral value."),
    "studied_formula": "The complete formula is assessed against its studied dose.",
    "panel": "The nutrient panel is assessed as a whole: required coverage, critical nutrients and any prenatal complement.",
    "b_complex_panel": "The fixed B-vitamin panel is assessed; each vitamin counts equally.",
    "omega_purpose_reference": "EPA+DHA (DHA for prenatal products) is assessed against the reference for the product's purpose.",
    "fiber_aggregate": "The disclosed fiber is assessed as one aggregate amount.",
    "single_profile_assessment": "One category profile assesses the main active against an applicable reference, or records a completed neutral when none applies.",
}
_ASSESSMENT_COPY = {
    "panel_component": ("recorded rubric contribution", "pharmaguide_policy"),
    "contribution_policy_target": ("PharmaGuide contribution target (20% of the FDA Daily Value)", "pharmaguide_policy"),
    "dri_reference": ("RDA/AI", "nutritional_reference"),
    "clinical_anchor": ("reviewed clinical anchor", "clinical_reference"),
    "legacy_reference": ("reference intake (interim)", "nutritional_reference"),
    "clinical_benchmark": ("studied preparation benchmark", "clinical_reference"),
    "aggregate_formula_benchmark": ("studied formula benchmark", "clinical_reference"),
    "no_benchmark_neutral": ("no applicable benchmark: neutral value", "pharmaguide_policy"),
    "hidden_amount_neutral": ("amount hidden: neutral value", "pharmaguide_policy"),
}


def _dose_aggregation(module: Optional[str], metadata: Dict[str, Any]) -> Optional[str]:
    for key in ("dose_participation_basis", "dose_aggregation"):
        value = metadata.get(key)
        if value in _AGGREGATION_COPY:
            return value
    if metadata.get("dose_adequacy_basis") == "studied_formula_native_afu" or (
            (metadata.get("studied_formula_assessment") or {}).get("status") == "assessed_studied_formula"):
        return "studied_formula"
    return {"multi_or_prenatal": "panel", "b_complex": "b_complex_panel", "omega": "omega_purpose_reference",
            "fiber_digestive": "fiber_aggregate"}.get(module or "")


def _dose_contributions(module: Optional[str], metadata: Dict[str, Any], factor: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for entry in metadata.get("dose_contributions") or []:
        if not isinstance(entry, dict) or _num(entry.get("credit_raw")) is None:
            continue
        label, kind = _ASSESSMENT_COPY.get(str(entry.get("assessment")), (
            str(entry.get("band") or entry.get("assessment") or "assessment").replace("_", " "), "clinical_reference"))
        assessment = str(entry.get("assessment") or "")
        if assessment.endswith("_contribution_policy"):
            label, kind = "PharmaGuide contribution target", "pharmaguide_policy"
        elif entry.get("band") == "blend_total_only":
            label, kind = "blend total only; individual amounts unknown", "pharmaguide_policy"
        elif (assessment.endswith("_completed_no_general_benchmark")
              or entry.get("band") in {"no_benchmark_neutral", "disclosed_no_reference"}):
            label, kind = "no applicable general benchmark: neutral value", "pharmaguide_policy"
        out.append({"ingredient": str(entry.get("ingredient") or ""), "assessment": entry.get("assessment"),
                    "reference": ("qualified printed amount; " + label if entry.get("quantity_operator") not in (None, "=")
                                  else label), "reference_kind": kind,
                    **{key: entry.get(key) for key in ("amount_at_minimum", "amount_at_maximum", "amount_unit",
                                                       "amount_per_serving", "reference_value", "pct_of_reference",
                                                       "absorption_context_per_administration_mg", "quantity_operator", "frequency_defaulted")
                       if entry.get(key) is not None},
                    "points": round(_num(entry["credit_raw"]) * factor, 2)})
    for strain in metadata.get("cfu_adequacy_contributions") or []:
        if isinstance(strain, dict) and _num(strain.get("points")) is not None:
            state = str(strain.get("state") or "measured")
            minimum_servings = _num((metadata.get("daily_use") or {}).get("minimum_servings"))
            minimum_cfu = _num(strain.get("cfu_per_day"))
            out.append({"ingredient": str(strain.get("strain") or strain.get("clinical_id") or "unlisted strain"), "assessment": state,
                        "reference": "strain CFU benchmark" if state == "measured" else state.replace("_", " "),
                        "reference_kind": "industry_potency_reference" if state == "measured" else "pharmaguide_policy",
                        "amount_at_minimum": strain.get("cfu_per_day"),
                        "amount_at_maximum": strain.get("maximum_cfu_per_day"), "amount_unit": "CFU",
                        "amount_per_serving": minimum_cfu / minimum_servings if minimum_cfu is not None and minimum_servings else None,
                        "points": round(_num(strain["points"]) * 3.0 * factor, 2)})
    reference = metadata.get("adequacy_reference")
    if isinstance(reference, dict) and _num(reference.get("target_mg_day")) is not None:
        omega = {"ingredient": "DHA" if reference.get("purpose") == "prenatal_dha" else "EPA + DHA",
                    "assessment": reference.get("purpose"), "reference": f"{reference['target_mg_day']:g} mg/day reference",
                    "reference_kind": "pharmaguide_policy" if reference.get("purpose") == "triglyceride" else "nutritional_reference",
                    "reference_value": reference.get("target_mg_day"), "amount_unit": "mg",
                    "amount_mg_day": reference.get("amount_mg_day"), "amount_at_minimum": reference.get("amount_mg_day")}
        minimum_servings = _num((metadata.get("daily_use") or {}).get("minimum_servings"))
        maximum_servings = _num((metadata.get("daily_use") or {}).get("maximum_servings"))
        if minimum_servings and _num(reference.get("amount_mg_day")) is not None:
            per_serving = _num(reference["amount_mg_day"]) / minimum_servings
            omega.update(amount_per_serving=per_serving,
                         amount_at_maximum=per_serving * maximum_servings if maximum_servings else None)
        if out:
            out[0].update(omega)
        else:
            out.append(omega)
    if metadata.get("fiber_dose_source") and out:
        out[0].update(amount_per_serving=metadata.get("fiber_grams_per_serving"),
                      amount_at_minimum=metadata.get("fiber_grams_daily_benchmark"),
                      amount_at_maximum=metadata.get("fiber_grams_daily_maximum"), amount_unit="g")
    return out


def _dose_receipt(pillar: Dict[str, Any], dose: Dict[str, Any], module: Optional[str]) -> Dict[str, Any]:
    metadata = dose.get("metadata") or {}
    components = pillar.get("components") or {}
    reference = _num(components.get("reference")) or 0.0
    weight = _num(pillar.get("max")) or 0.0
    factor = weight / reference if reference else 0.0
    score = _num(pillar.get("score"))
    adequacy = _num(components.get("adequacy_before_safety"))
    adequacy = score if adequacy is None else adequacy
    ceiling = (metadata.get("B7_safety_evaluation") or {}).get("dose_ceiling")
    upper = None
    if isinstance(ceiling, dict) and _num(ceiling.get("cap_public")) is not None:
        upper = {key: ceiling.get(key) for key in (
            "kind", "nutrient", "ul", "ul_unit", "ul_population", "pct_ul", "pct_ul_at_minimum", "amount_mg_day",
            "amount_mg_day_at_minimum", "exceeds_above_mg_day", "minimum_exceeds", "cap_public", "quantity_operator") if ceiling.get(key) is not None}
        upper["policy"] = "pharmaguide_scoring_policy"
    receipt = {
        "daily_use": metadata.get("daily_use"),
        "aggregation": _dose_aggregation(module, metadata),
        "contributions": _dose_contributions(module, metadata, factor),
        "reference_assessments": metadata.get("reference_assessments") or [],
        "adequacy_before_safety": adequacy,
        "upper_reference": upper,
        "final": score,
    }
    cap = _num((upper or {}).get("cap_public"))
    points = [_num(item.get("points")) for item in receipt["contributions"]]
    accounted = sum(p for p in points if p is not None)
    if receipt["aggregation"] in {"declared_purpose_equal_weight", "assessed_nutrient_average",
                                 "co_primary_average", "strain_average_with_neutral_states"} and points:
        accounted /= len(points)
    if (metadata.get("window_proxy_status") == "partial_credit_primary_active_unassessed"
            and metadata.get("primary_active_unassessed")
            and _num(metadata.get("partial_credit_value")) is not None):
        constraint = _num(metadata["partial_credit_value"]) * factor
        receipt["primary_active_unassessed"] = metadata["primary_active_unassessed"]
        receipt["partial_credit_value"] = round(constraint, 2)
        accounted = min(accounted, constraint)
    if dose.get("score") is None:
        # A partial assessment has no final Dose arithmetic. Preserve its
        # diagnostic contributions without presenting the placeholder0 as a
        # completed score or a neutral award.
        receipt.update(assessment_status="incomplete", adequacy_before_safety=None,
                       final=None, reconciles=None)
        return receipt
    receipt["reconciles"] = (score is not None and adequacy is not None
                             and abs(adequacy - min(weight, accounted)) < 0.051
                             and abs(score - (min(adequacy, cap) if cap is not None else adequacy)) < 0.05)
    return receipt


def _ingredient_display(item: Dict[str, Any], receipt: Dict[str, Any]) -> str:
    """The display name for a receipt contribution, never its canonical ID.

    Contributions key on the scorer's identity, which may be a canonical ID
    (``vitamin_c``). The source-owned reference row carries the display name;
    without one, the ID is spelled as words.
    """
    ingredient = str(item.get("ingredient") or "")
    for row in receipt.get("reference_assessments") or []:
        if isinstance(row, dict) and row.get("nutrient") and row.get("canonical_id") == ingredient:
            return str(row["nutrient"])
    return ingredient.replace("_", " ")


def _dose_consumer_fact(receipt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The one Dose fact users see: the upper-limit result when a cap applies,
    otherwise one assessed amount against its reference, otherwise the honest
    disclosure gap. Built only from the receipt; nothing is recomputed."""
    daily_use = receipt.get("daily_use") or {}
    upper = receipt.get("upper_reference")
    if upper:
        if upper.get("kind") == "caffeine_daily_total":
            amount, reference = _num(upper.get("amount_mg_day")), _num(upper.get("exceeds_above_mg_day"))
            if amount is None or reference is None:
                return None
            value = (f"{'At one serving a day' if daily_use.get('defaulted') else 'Up to'} {_amount(amount)} mg "
                     f"of caffeine a day; reference {_amount(reference)} mg a day for most adults")
        else:
            pct, limit = _num(upper.get("pct_ul")), _num(upper.get("ul"))
            if pct is None or limit is None:
                return None
            unit = upper.get("ul_unit") or ""
            rows = [row for row in receipt.get("reference_assessments") or []
                    if isinstance(row, dict) and row.get("nutrient") == upper.get("nutrient")]
            highest = _num(rows[0].get("per_day_max")) if len(rows) == 1 else None
            if highest is not None and abs(highest - limit * pct / 100) > max(1.0, highest * 0.01):
                highest = None  # the row is not the exposure the ceiling compared
            if daily_use.get("defaulted"):
                exposure = "At one serving a day"
            elif highest is not None:
                same = _num(daily_use.get("minimum_servings")) == _num(daily_use.get("maximum_servings"))
                exposure = f"{'' if same else 'Up to '}{_amount(highest)} {unit} a day".strip()
                exposure = exposure[0].upper() + exposure[1:]
            else:
                exposure = "At the highest directed use"
            value = (f"{exposure}: {pct:.0f}% of the {_amount(limit)} {unit} {upper.get('nutrient')} "
                     f"upper limit ({upper.get('ul_population') or 'general adult'})")
        return {"id": "dose_upper_limit_result", "label": "Upper limit", "value_display": value, "audience": CONSUMER}
    contributions = receipt.get("contributions") or []
    if len(contributions) == 1:
        item = contributions[0]
        low, high = _num(item.get("amount_at_minimum")), _num(item.get("amount_at_maximum"))
        reference, unit = _num(item.get("reference_value")), item.get("amount_unit")
        if (low is not None and reference is not None and unit
                and item.get("quantity_operator") in (None, "=")):
            label = str(item.get("reference") or "")
            reference_name = ("RDA/AI" if label.startswith("RDA/AI")
                              else "PharmaGuide target" if label.startswith("PharmaGuide contribution target")
                              else "reference")
            span = _amount(low) if high in (None, low) else f"{_amount(low)}-{_amount(high)}"
            return {"id": "dose_amount_vs_reference", "label": "Amount vs reference",
                    "value_display": (f"{span} {unit} {_ingredient_display(item, receipt)} a day; "
                                      f"{reference_name} {_amount(reference)} {unit}"),
                    "audience": CONSUMER}
    states = {str(item.get("assessment")) for item in contributions}
    if contributions and states == {"neutral_amount_not_disclosed"}:
        return {"id": "dose_amount_gap", "label": "Not on the label",
                "value_display": "Per-strain amounts are not listed", "audience": CONSUMER}
    if contributions and states == {"hidden_amount_neutral"}:
        return {"id": "dose_amount_gap", "label": "Not on the label",
                "value_display": "Individual ingredient amounts are not listed", "audience": CONSUMER}
    return None


def _dose_receipt_facts(receipt: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    if receipt.get("assessment_status") == "incomplete":
        return [{"id": "dose_assessment_incomplete", "label": "Dose assessment incomplete",
                 "value_display": "A required ingredient amount could not be assessed", "audience": CONSUMER},
                audit_fact("dose_assessment_incomplete_detail", "Dose assessment incomplete",
                           "Known ingredient contributions do not establish a final Dose score.")]
    consumer = _dose_consumer_fact(receipt)
    if consumer is not None:
        facts.append(consumer)
    aggregation = receipt.get("aggregation")
    contributions = receipt.get("contributions") or []
    if contributions:
        def amounts(item: Dict[str, Any]) -> str:
            low, high, unit = _num(item.get("amount_at_minimum")), _num(item.get("amount_at_maximum")), item.get("amount_unit") or ""
            if low is None:
                return ""
            operator = item.get("quantity_operator") or ""
            operator = "" if operator == "=" else operator
            span = f"{operator}{low:g} {unit}/day" if high in (None, low) else f"{operator}{low:g}-{high:g} {unit}/day"
            defaulted = item.get("frequency_defaulted", (receipt.get("daily_use") or {}).get("defaulted"))
            basis = "at the default of one serving a day" if defaulted else "by directions"
            return f", {span} {basis}".replace(" /day", "/day")

        shown = "; ".join(
            f"{_ingredient_display(item, receipt)}: {item['reference']}"
            + (f" {item['reference_value']:g} {item.get('amount_unit') or ''}".rstrip() if _num(item.get("reference_value")) is not None else "")
            + amounts(item)
            + (f", {item['pct_of_reference']:.0f}% of it at the lowest daily use" if _num(item.get("pct_of_reference")) is not None else "")
            + (f", {item['amount_mg_day']:g} mg/day at the lowest daily use" if _num(item.get("amount_mg_day")) is not None else "")
            + (f" ({item['points']:g} points)" if _num(item.get("points")) is not None else "")
            for item in contributions[:6])
        more = f"; and {len(contributions) - 6} more" if len(contributions) > 6 else ""
        facts.append({"id": "dose_contributions", "label": "What Dose assessed",
                      "value_display": shown + more + ".",
                      **({"detail": _AGGREGATION_COPY[aggregation]} if aggregation in _AGGREGATION_COPY else {})})
    elif aggregation in _AGGREGATION_COPY:
        facts.append({"id": "dose_contributions", "label": "What Dose assessed", "value_display": _AGGREGATION_COPY[aggregation]})
    for item in contributions:
        per_serving, context = _num(item.get("amount_per_serving")), _num(item.get("absorption_context_per_administration_mg"))
        if per_serving is not None and context is not None and per_serving > context:
            facts.append({"id": "dose_absorption_context", "label": "Absorption context",
                          "value_display": (
                              f"One serving provides {per_serving:g} {item.get('amount_unit') or 'mg'} of {_ingredient_display(item, receipt)}. "
                              f"NIH notes the body absorbs calcium best in amounts of {context:g} mg or less at a time. "
                              "This is context only and does not change the score.")})
    if aggregation in {"panel", "b_complex_panel"}:
        for index, row in enumerate(receipt.get("reference_assessments") or []):
            low, high = _num(row.get("per_day_min")), _num(row.get("per_day_max"))
            reference, pct = _num(row.get("rda_ai")), _num(row.get("pct_rda"))
            if reference is None or pct is None:
                continue
            exposure = ""
            if low is not None:
                span = f"{low:g}" if high in (None, low) else f"{low:g}-{high:g}"
                exposure = f"{span} {row.get('unit') or ''}/day; "
            population = f" ({row['reference_population']})" if row.get("reference_population") else ""
            facts.append({"id": f"dose_panel_reference_{index}", "label": str(row.get("nutrient") or "Panel nutrient"),
                          "value_display": f"{exposure}{pct:g}% of the assessed RDA/AI{population} at the lowest daily use."})
    if receipt.get("primary_active_unassessed") and _num(receipt.get("partial_credit_value")) is not None:
        facts.append({"id": "dose_primary_reference_gap", "label": "Primary active reference gap",
                      "value_display": (
                          f"The main active {str(receipt['primary_active_unassessed']).replace('_', ' ')} has no applicable reference. "
                          f"The existing assessment limits adequacy to {receipt['partial_credit_value']:g}/20; "
                          "the assessed secondary nutrients cannot establish the main active's dose adequacy.")})
    metadata = metadata or {}
    if str(metadata.get("critical_nutrient_mode") or "").startswith("prenatal"):
        row = next((r for r in receipt.get("reference_assessments") or []
                    if str(r.get("canonical_id") or r.get("nutrient") or "").lower() == "choline"), None)
        amount = _num((row or {}).get("per_day_min"))
        pct = _num((row or {}).get("pct_rda"))
        if amount is not None and pct is not None:
            broad = _num((metadata.get("coverage_nutrient_scores") or {}).get("choline"))
            critical = _num((metadata.get("critical_nutrient_scores") or {}).get("choline"))
            text = (f"This prenatal provides {amount:g} {(row or {}).get('unit') or 'mg'} per minimum directed day, "
                    f"approximately {pct:g}% of the pregnancy Adequate Intake. "
                    "The full AI includes food and is not a required supplement amount. "
                    f"Recorded broad panel coverage: {broad:g}; critical prenatal coverage: {critical:g} "
                    "on the contribution scale from0 to1, not percent effectiveness.")
        else:
            text = ("No choline contribution identified. Choline is included in PharmaGuide's critical prenatal nutrient review. "
                    "Food can contribute choline, so this does not mean the user's total intake is zero. "
                    "The full AI includes food and is not a required supplement amount.")
        facts.append({"id":"dose_prenatal_choline", "label":"Choline contribution", "value_display":text})
    upper = receipt.get("upper_reference")
    adequacy, final = _num(receipt.get("adequacy_before_safety")), _num(receipt.get("final"))
    if upper:
        if upper.get("kind") == "caffeine_daily_total":
            qualifier = {">=": "At least ", ">": "More than "}.get(upper.get("quantity_operator"), "")
            limit = (f"{qualifier}{_num(upper.get('amount_mg_day')):g} mg of caffeine a day at the highest directed use, against "
                     f"the {_num(upper.get('exceeds_above_mg_day')):.0f} mg/day reference for most adults")
        else:
            at_min = _num(upper.get("pct_ul_at_minimum"))
            limit = (f"{_num(upper.get('pct_ul')):.0f}% of the {upper.get('nutrient')} upper limit"
                     + (f" of {_num(upper.get('ul')):g} {upper.get('ul_unit') or ''}".rstrip() if _num(upper.get("ul")) else "")
                     + f" ({upper.get('ul_population') or 'general adult'} limit) at the highest directed use"
                     + (f", {at_min:.0f}% at the lowest" if at_min is not None else ""))
        facts.append({"id": "dose_upper_reference", "label": "Upper-limit check",
                      "value_display": f"{limit}; Dose is capped at {_num(upper['cap_public']):g} (PharmaGuide scoring policy)."})
    if adequacy is not None and final is not None:
        if upper:
            arithmetic = (f"Adequacy {adequacy:g}/20, capped at {_num(upper['cap_public']):g}: Dose {final:g}/20.")
        else:
            arithmetic = f"Adequacy {adequacy:g}/20; no upper-limit cap applies: Dose {final:g}/20."
        facts.append({"id": "dose_arithmetic", "label": "How Dose adds up", "value_display": arithmetic})
    return facts


_FACT_BUILDERS = {
    "dose": _omega_dose_facts,
    "formulation": _omega_formulation_facts,
}


def attach_pillar_explanations(
    pillars: Dict[str, Any],
    module_bd: Dict[str, Any],
    cfg: Dict[str, Any],
    module: Optional[str],
) -> Dict[str, Any]:
    """Attach optional ``explanation`` blocks to ``pillars`` in place.

    Returns ``pillars`` for convenience. Facts are built only from the module
    breakdown metadata the scorer already produced; absent inputs emit no fact.
    Facts a pillar builder already attached (a reason's moved detail) are kept
    first. Any fact without an ``audience`` is audit detail.
    """
    dims = (module_bd or {}).get("dimensions") or {}
    specs = (cfg or {}).get("pillars") or {}
    dim_by_assembler = {"dose": dims.get("dose") or {}, "formulation": dims.get("formulation") or {}}

    for name, spec in specs.items():
        pillar = pillars.get(name)
        if not isinstance(pillar, dict):
            continue
        assembler = spec.get("assembler")
        facts: List[Dict[str, Any]] = list((pillar.get("explanation") or {}).get("facts") or [])
        builder = _FACT_BUILDERS.get(assembler) if module == "omega" else None
        if builder is not None:
            facts.extend(builder(dim_by_assembler.get(assembler) or {}))
        if assembler == "dose":
            metadata = ((dims.get("dose") or {}).get("metadata") or {})
            if metadata.get("assessment_basis") == "directed_daily_use":
                daily_use = metadata.get("daily_use") or {}
                facts.append({
                    "id": "dose_reference_method", "label": "Dose assessment basis",
                    "value_display": (
                        "Dose uses recorded nutrient references and applicable preparation benchmarks. "
                        + ("The label gives no daily directions, so one serving a day is assessed. "
                           if daily_use.get("defaulted") else
                           "Adequacy uses the lowest directed daily use; upper-limit checks use the highest. ")
                        + "These are catalog assessments, not a personal dose recommendation."),
                })
            if metadata.get("method") == "source_qualified_contribution_and_completed_neutral":
                assessment = {key: metadata.get(key) for key in (
                    "method", "assessment_basis", "daily_use", "reference_assessments",
                    "supplemental_window_max_raw", "positive_clinical_benchmark_assessments",
                    "dose_participation_basis", "unbenchmarked_purpose_ingredients",
                )}
                assessment["raw_dose"] = (pillar.get("components") or {}).get("raw_dose")
                assessment["normalization_reference"] = (pillar.get("components") or {}).get("reference")
                pillar["explanation"] = {**(pillar.get("explanation") or {}),
                                         "schema_version": PILLAR_EXPLANATION_SCHEMA_VERSION, "assessment": assessment}
            ceiling = ((metadata.get("B7_safety_evaluation") or {}).get("dose_ceiling") or {})
            if _num(ceiling.get("cap_public")) is not None:
                if ceiling.get("kind") == "caffeine_daily_total":
                    rule = (f"When the highest directed daily use provides more than {ceiling['exceeds_above_mg_day']:g} mg "
                            f"of caffeine, Dose is at most {ceiling['partial_ceiling_public']:g}; at "
                            f"{ceiling['zero_at_mg_day']:g} mg/day or more it is 0. Single doses above 200 mg are "
                            "a separate consideration, even within a daily amount. ")
                else:
                    rule = (f"When the highest directed daily use exceeds an established upper limit, Dose is at most "
                            f"{ceiling['partial_ceiling_public']:g}; at {ceiling['zero_at_pct']:g}% of the limit or more it is 0. ")
                facts.append({
                    "id": "dose_safety_ceiling", "label": "Upper-limit scoring rule",
                    "value_display": (
                        rule
                        + "This product-level cap is applied once, after the ingredient assessment, and never raises a lower score. "
                        "It is PharmaGuide scoring policy, not a medical toxicity grade. "
                        "The applicable reference determines which food, supplement or medication sources count; their limits are not interchangeable."
                    ),
                })
            purpose_count = _nonnegative_int(metadata.get("purpose_ingredient_count"))
            unbenchmarked = metadata.get("unbenchmarked_purpose_ingredients")
            if (purpose_count and isinstance(unbenchmarked, list) and unbenchmarked
                    and all(isinstance(item, str) and item for item in unbenchmarked)
                    and len(unbenchmarked) <= purpose_count):
                facts.append({
                    "id": "dose_reference_availability",
                    "label": "Dose reference availability",
                    "value_display": (
                        f"{len(unbenchmarked)} of {purpose_count} purpose ingredients "
                        "have disclosed amounts but no applicable dose benchmark. "
                        "Their adequacy cannot be determined confidently from available evidence; "
                        "they remain included with limited-assessment credit."
                    ),
                })
            if _num((pillar.get("components") or {}).get("reference")):
                # Only an assembled public pillar has the reference that
                # converts raw credits; a bare legacy pillar keeps its reason.
                dose_receipt = _dose_receipt(pillar, dims.get("dose") or {}, module)
                pillar["explanation"] = {**(pillar.get("explanation") or {}),
                                         "schema_version": PILLAR_EXPLANATION_SCHEMA_VERSION,
                                         "dose_receipt": dose_receipt}
                facts.extend(_dose_receipt_facts(dose_receipt, (dims.get("dose") or {}).get("metadata") or {}))
            assessments = ((dims.get("dose") or {}).get("metadata") or {}).get("clinical_exposure_assessments") or []
            for index, assessment in enumerate(assessments):
                if isinstance(assessment, dict) and assessment.get("kind") == "studied_regimen" and assessment.get("notes"):
                    facts.append({
                        "id": f"clinical_research_exposure_{index}",
                        "label": str(assessment.get("name") or "Research exposure"),
                        "value_display": assessment["notes"],
                    })
        if assembler == "evidence":
            facts.extend(_zero_evidence_facts(pillar, dims.get("evidence") or {}))
        if spec.get("source_dim") == "transparency":
            facts.extend(_proprietary_blend_facts(dims.get("transparency") or {}))
        unique: Dict[tuple, Dict[str, Any]] = {}
        for fact in facts:
            # Re-attaching the same pillars must not repeat a fact.
            unique.setdefault((fact.get("id"), fact.get("value_display")),
                              {**fact, "audience": fact.get("audience") or AUDIT})
        facts = list(unique.values())
        if facts:
            pillar["explanation"] = {
                **(pillar.get("explanation") or {}),
                "schema_version": PILLAR_EXPLANATION_SCHEMA_VERSION,
                "facts": facts,
            }
    return pillars
