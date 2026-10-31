"""PharmaGuide public six-pillar Quality Score — decision score assembler.

The public consumer score, separate from the raw v4 audit/math score. Six pillars:
formulation/20, dose/20, evidence/20, transparency/15, verification/15, safety_hygiene/10.

Current state: the public score is assembled from category-aware pillar adapters,
not a post-hoc display stretch. Formulation, dose, and evidence normalize against
archetype-specific achievable ceilings; verification ranks evidence tiers (unknown <
claim/brand < manufacturing < product-level); transparency remains a faithful source-dimension map because it
does not have the same structural ceiling problem.

INVARIANTS:
- ``raw_score_v4_100`` (== existing ``raw_score_v4_100``) is NEVER changed.
- BLOCKED / UNSAFE suppress the public quality score (show verdict + reasons instead).
- NOT_SCORED / null raw → ``not_scored`` status, null score.
- Every pillar carries a one-line human-readable reason (white box, no black box).
"""
from __future__ import annotations

import math

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scoring_v4.dose_safety import dose_safety_consumer_explanation
from scoring_v4.penalty_registry import (
    EVIDENCE_CAP_KEYS,
    EVIDENCE_FLOOR_KEYS,
    component_kind,
    penalty_spec,
)
from scoring_v4.pillar_explanations import (
    CONSUMER, attach_pillar_explanations, audit_fact, facts_block, _proprietary_blend_facts,
)

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "quality_score.json"
_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = json.loads(_CONFIG_PATH.read_text())
    return copy.deepcopy(_CONFIG_CACHE)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _component_num(components: Dict[str, Any], *keys: str) -> float:
    for key in keys:
        if key in components:
            return _num(components.get(key))
    return 0.0


def _g(value: float) -> str:
    return f"{value:g}"


# ── Consumer-facing reason copy ──────────────────────────────────────────────
# The pillar ``reason`` strings ship to end users in the app's "How it scores"
# UI, so they must read as plain English a supplement shopper understands — no
# internal scoring vocabulary (archetype/breadth/phase names, raw fractions,
# arrows, module names). Each pillar maps its score → a short, honest sentence
# banded on how full the pillar is. The numeric score itself is unchanged and
# still shown separately; these strings only EXPLAIN it. When a pillar is low
# because the underlying signal is weak, the copy says so plainly (honesty over
# flattery — under-warning is the worse failure for a health product).

def _band(score: float, weight: float) -> str:
    """Coarse fullness band for a pillar's score → {high, mid, low}."""
    if weight <= 0:
        return "low"
    ratio = score / weight
    if ratio >= 0.8:
        return "high"
    if ratio >= 0.5:
        return "mid"
    return "low"


def _reason_formulation(band: str) -> str:
    return {
        "high": "Well-formulated — uses high-quality, well-absorbed ingredient forms.",
        "mid": "Uses reasonable ingredient forms, with room for more premium options.",
        "low": "Uses basic or low-cost ingredient forms.",
    }[band]


def evidence_pillar_reason_is_affirmative(pillar: Dict[str, Any]) -> bool:
    """Whether the scorer's Evidence headline is an earned positive result.

    Result state alone is not enough: ``evaluated_applicable`` can describe
    either strong support or genuinely limited evidence, and authority review
    can earn zero points. Keep this decision beside the band/reason owner so
    export consumers never infer sentiment from prose.
    """
    try:
        score = float(pillar.get("score"))
        maximum = float(pillar.get("max"))
    except (TypeError, ValueError):
        return False
    state = str(pillar.get("evidence_result_state") or "").strip()
    if state in {"evaluated_authority", "authority_supported"}:
        return score > 0
    return state == "evaluated_applicable" and _band(score, maximum) in {
        "mid",
        "high",
    }


def formulation_pillar_reason_is_affirmative(
    pillar: Dict[str, Any],
    dimension: Dict[str, Any],
) -> bool:
    """Whether the scorer-authored Formulation headline is wholly positive.

    High generic and route credit is affirmative, but a high numeric score can
    still carry a real omega/profile limitation. Use the same structured
    metadata that authors the headline rather than matching consumer strings.
    """
    try:
        score = float(pillar.get("score"))
        maximum = float(pillar.get("max"))
    except (TypeError, ValueError):
        return False
    if _band(score, maximum) != "high":
        return False

    components = pillar.get("components") or {}
    archetype = str(components.get("archetype") or "").strip()
    metadata = dimension.get("metadata") or {}
    if archetype == "omega":
        form_code = str(metadata.get("form_detected") or "").strip().lower()
        concentration = metadata.get("epa_dha_concentration")
        ratio = concentration.get("ratio") if isinstance(concentration, dict) else None
        return (
            form_code in _OMEGA_MOLECULAR_FORM_COPY
            and isinstance(ratio, (int, float))
            and not isinstance(ratio, bool)
            and ratio >= 0
        )

    profile_reason = _profile_formulation_reason(metadata)
    if profile_reason is not None:
        lowered = profile_reason.lower()
        return (
            pillar.get("reason") == profile_reason
            and "not credited:" not in lowered
            and "no formulation credit" not in lowered
        )

    route_reason = _route_formulation_reason(dimension, "high")
    expected_reason = route_reason or _reason_formulation("high")
    return pillar.get("reason") == expected_reason


_OMEGA_MOLECULAR_FORM_COPY = {
    "tg": "triglyceride",
    "rtg": "re-esterified triglyceride",
    "pl": "phospholipid",
    "ee": "ethyl ester",
}


#: (identity key and its neutral wording, earned traits, traits named when absent).
#: V4.1 Step 4: identity is neutral credit; plant part, amount, type, source and
#: brand earn nothing here (Transparency and Evidence own them).
_PROFILE_COPY = {
    "botanical_formulation": (
        ("recognized_botanical_identity", "recognized botanical identity"),
        # A partial standardization tier is still credited, so the label does
        # not claim the marker met its full specification.
        (("extract_not_whole_herb", "extract preparation"),
         ("marker_standardization_declared", "marker standardization")),
        (("marker_standardization_declared", "marker standardization"),),
    ),
    "collagen_formulation": (
        ("recognized_collagen_identity", "recognized collagen identity"),
        (("hydrolyzed_peptides", "hydrolyzed peptides"),),
        (("hydrolyzed_peptides", "hydrolyzed peptides"),),
    ),
}

#: Formulation engines that do not rate ingredient forms, and what they credit.
_ROUTE_FORMULATION_SUBJECT = (
    ("sports_protein_", "protein source quality"),
    ("fiber_", "fiber source quality"),
)


def _profile_formulation_reason(metadata: Dict[str, Any]) -> Optional[str]:
    """Name the botanical/collagen facts that earned (and did not earn) points."""
    profile = _profile_detail(metadata)
    if profile is None:
        return None
    section, detail = profile
    if section == "botanical_formulation" and _num(detail.get("weak_or_unidentified_botanical")) < 0:
        blend = metadata.get("botanical_unverified_blend")
        if isinstance(blend, dict) and blend.get("name"):
            amount = _num(blend.get("amount_mg"))
            label = f"{blend['name']}, {amount:g} mg" if amount > 0 else str(blend["name"])
            reason = (f"The main botanical blend ({label}) is disclosed, but its exact preparation "
                      "cannot be verified for Formulation scoring.")
            if blend.get("separately_identified"):
                reason += " Other identified ingredients are assessed separately."
            return reason
        return "Botanical identity could not be confirmed, so no formulation credit was given."
    (identity_key, identity_label), credited_map, missing_map = _PROFILE_COPY[section]
    credited = [label for key, label in credited_map if _num(detail.get(key)) > 0]
    missing = [label for key, label in missing_map if _num(detail.get(key)) <= 0]
    parts = []
    if _num(detail.get(identity_key)) > 0:
        parts.append(f"The {identity_label} receives neutral credit")
    if credited:
        parts.append(("credited: " if parts else "Credited: ") + ", ".join(credited))
    if missing:
        parts.append(("not credited: " if parts else "Not credited: ") + ", ".join(missing))
    return ("; ".join(parts) + ".") if parts else "No formulation credit."


def _route_formulation_reason(dim: Dict[str, Any], band: str) -> Optional[str]:
    """Band copy for engines that score something other than ingredient forms."""
    keys = list((dim.get("components") or {}).keys())
    for prefix, subject in _ROUTE_FORMULATION_SUBJECT:
        if any(key.startswith(prefix) for key in keys):
            level = {"high": "Strong", "mid": "Partial", "low": "Limited"}[band]
            return f"{level} formulation credit for {subject}."
    return None


def _omega_formulation_reason(dim: Dict[str, Any], fallback: str) -> str:
    """Explain omega formulation from the signals that produced its score.

    A bare parent identity such as ``Fish Oil`` is not a molecular-form
    disclosure. The omega formulation module records that distinction in
    ``form_detected`` and separately records label-derived EPA+DHA
    concentration; this adapter describes both without changing either score.
    """
    metadata = dim.get("metadata") if isinstance(dim, dict) else None
    if not isinstance(metadata, dict) or "form_detected" not in metadata:
        return fallback

    form_code = str(metadata.get("form_detected") or "").strip().lower()
    form_name = _OMEGA_MOLECULAR_FORM_COPY.get(form_code)
    if form_name:
        form_clause = f"Molecular form is disclosed as {form_name}"
    elif form_code == "undefined":
        form_clause = "Molecular form is not disclosed on the label"
    else:
        form_clause = "Molecular-form data needs review"

    concentration = metadata.get("epa_dha_concentration")
    if not isinstance(concentration, dict):
        return form_clause + "."

    ratio = concentration.get("ratio")
    if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and ratio >= 0:
        percentage = round(float(ratio) * 100, 1)
        percentage_display = _g(percentage)
        return (
            f"{form_clause}; EPA + DHA make up {percentage_display}% of the "
            "disclosed omega-oil amount."
        )

    return (
        f"{form_clause}; EPA + DHA concentration could not be calculated from "
        "the disclosed amounts."
    )


def _reason_dose(band: str) -> str:
    return {
        "high": "Doses receive high credit against the applicable PharmaGuide dose benchmarks.",
        "mid": "Doses receive partial credit against the applicable PharmaGuide dose benchmarks.",
        "low": "Doses receive limited credit against the applicable PharmaGuide dose benchmarks.",
    }[band]


def _probiotic_dose_reason(dim: Dict[str, Any], fallback: str) -> str:
    """Explain an unverifiable per-strain dose without calling total CFU low."""
    metadata = dim.get("metadata") if isinstance(dim, dict) else None
    if not isinstance(metadata, dict):
        return fallback
    if metadata.get("reason_code") == "probiotic_afu_reference_unavailable":
        return "AFU amounts are disclosed, but a compatible dose benchmark has not been verified."
    if metadata.get("dose_adequacy_basis") == "studied_formula_native_afu":
        return "The complete formula matches its studied AFU dose; individual strain amounts are not disclosed."
    # Dose V4.1 section 2.3: a hidden per-strain amount or a missing benchmark
    # takes the shared neutral; neither means the product is underdosed, and
    # Transparency keeps the disclosure consequence.
    basis = _probiotic_cfu_basis(metadata)
    if basis == "aggregate_cfu_disclosed_only":
        return (
            "Total potency is disclosed, but per-strain amounts are not, so they cannot "
            "be checked against strain dose benchmarks; Dose takes the neutral assessment value."
        )
    if basis == "direct_strain_mass_no_cfu_floor":
        return ("Strain amounts are given by weight, not live count, so they cannot be "
                "checked against strain dose benchmarks; Dose takes the neutral assessment value.")
    if basis == "no_cfu_adequacy_credit":
        tiers = {str(item.get("tier")) for item in metadata.get("cfu_adequacy_contributions") or []
                 if isinstance(item, dict)}
        if "low" in tiers:
            return ("Disclosed per-strain amounts are below the dose benchmarks for the strains "
                    "that have one, so they earn no dose credit.")
        if _num(metadata.get("per_strain_cfu_disclosed_count")) > 0:
            return ("Per-strain amounts are disclosed, but no strain dose benchmark applies, "
                    "so Dose takes the neutral assessment value.")
        return ("No live count (CFU) is disclosed, so dose adequacy cannot be assessed; "
                "Dose takes the neutral assessment value.")
    if metadata.get("reference_basis") == "completed_no_general_strain_benchmark":
        return ("Per-strain amounts are disclosed, but no general clinical dose benchmark applies; "
                "Dose takes the neutral assessment value.")
    if metadata.get("reference_basis") == "industry_potency_not_trial_efficacy":
        if _num(metadata.get("strain_neutral_count")) > 0:
            return ("Strains with a disclosed CFU are assessed against potency benchmarks; strains without "
                    "an assessable amount or benchmark take the neutral value, and Dose averages them; "
                    "potency benchmarks are not proof of clinical benefit.")
        return "Disclosed CFU is assessed against potency benchmarks, not proof of clinical benefit."
    return fallback


def _probiotic_cfu_basis(metadata: Dict[str, Any]) -> Optional[str]:
    # The Dose owner records the same limitation in window_proxy_reason; read
    # it when a payload carries only that field, never the underdose fallback.
    return metadata.get("cfu_adequacy_basis") or {
        "aggregate_cfu_not_per_strain": "aggregate_cfu_disclosed_only",
        "per_strain_cfu_missing": "no_cfu_adequacy_credit",
    }.get(str(metadata.get("window_proxy_reason") or ""))


def _probiotic_dose_facts(dim: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detail that once trailed the probiotic Dose reason, kept for audits."""
    metadata = dim.get("metadata") if isinstance(dim, dict) else None
    if (not isinstance(metadata, dict) or metadata.get("reason_code") == "probiotic_afu_reference_unavailable"
            or metadata.get("dose_adequacy_basis") == "studied_formula_native_afu"):
        return []
    if (_probiotic_cfu_basis(metadata) == "aggregate_cfu_disclosed_only"
            and str((metadata.get("cfu_guarantee") or {}).get("type") or "") == "unknown"):
        return [audit_fact("cfu_guarantee", "Potency guarantee",
                           "Whether the count is guaranteed through expiration is not stated.")]
    return []


def _undisclosed_component_dose_reason(dim: Dict[str, Any]) -> Optional[str]:
    """Explain an opaque blend without pretending its components are underdosed."""
    metadata = dim.get("metadata") if isinstance(dim, dict) else None
    if not isinstance(metadata, dict):
        return None
    if "blend_total_only" in (metadata.get("botanical_dose_band"), metadata.get("collagen_dose_band")):
        return (
            "The blend total is disclosed, but individual ingredient amounts aren't."
        )
    if any(isinstance(item, dict) and item.get("band") in {"blend_total_only", "primary_no_dose"}
           and isinstance(item.get("metadata"), dict)
           and item["metadata"].get("assessment_status") == "complete"
           and item["metadata"].get("reason_code") == "amount_not_declared"
           for item in metadata.get("specialized_purpose_assessments") or []):
        return "Some blend ingredients do not have individual amounts listed."
    if metadata.get("not_evaluable_reason") == "opaque_primary_sports_blend":
        reason = "The main ingredient's amount is hidden in a proprietary blend, so its dose cannot be assessed"
        return reason + ("; Dose takes the neutral assessment value." if _num(dim.get("score"), 0) > 0 else ".")
    return None


def _unassessed_primary_dose_reason(dim: Dict[str, Any]) -> Optional[str]:
    """Say why dose credit is partial when the main active has no benchmark."""
    metadata = dim.get("metadata") if isinstance(dim, dict) else None
    if not isinstance(metadata, dict):
        return None
    bands = (metadata.get("botanical_dose_band"), metadata.get("collagen_dose_band"))
    if "amount_not_assessable" in bands:
        return "The printed amount could not be read yet, so its dose has not been assessed."
    if "primary_no_dose" in bands:
        return "No amount is disclosed for the main ingredient, so its dose cannot be assessed."
    if (metadata.get("botanical_dose") or {}).get("benchmark") == "unresolved":
        return "The amount is disclosed, but the applicable dose benchmark review is incomplete."
    if "disclosed_no_reference" in bands or metadata.get("window_proxy_status") in {
        "partial_credit_without_rda_proxy",
        "partial_credit_primary_active_unassessed",
        "limited_assessability_unbenchmarked_purpose",
    }:
        return (
            "Dose disclosed, but adequacy cannot be determined confidently "
            "from available evidence because an applicable dose benchmark is unavailable."
        )
    return None


def _dose_ceiling(dim: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The one product-level Dose ceiling recorded by scoring_v4.dose_safety."""
    metadata = dim.get("metadata") if isinstance(dim, dict) else None
    evaluation = metadata.get("B7_safety_evaluation") if isinstance(metadata, dict) else None
    ceiling = evaluation.get("dose_ceiling") if isinstance(evaluation, dict) else None
    return ceiling if isinstance(ceiling, dict) and (
        _num(ceiling.get("cap_public"), -1) >= 0 or _num(ceiling.get("deduction_public"), -1) >= 0) else None


def _over_limit_dose_reason(dim: Dict[str, Any]) -> Optional[str]:
    """Explain a confirmed excess and the ceiling it sets."""
    metadata = dim.get("metadata") if isinstance(dim, dict) else None
    if not isinstance(metadata, dict):
        return None
    evaluation = metadata.get("B7_safety_evaluation")
    if not isinstance(evaluation, dict):
        return None
    ceiling = _dose_ceiling(dim)
    if ceiling is not None:
        nutrient = str(ceiling.get("nutrient") or "One nutrient")
        cap = _num(ceiling.get("cap_public"))
        outcome = ("so a small deduction applies to the Dose credit earned at the lowest directed use"
                   if ceiling.get("deduction_public") is not None else
                   "so Dose credit is withheld" if cap == 0 else "so Dose credit is limited")
        if ceiling.get("kind") == "caffeine_daily_total":
            use = ("at one serving a day (the label gives no daily amount)" if ceiling.get("frequency_defaulted")
                   else "even at the lowest directed daily use" if ceiling.get("minimum_exceeds")
                   else "at the highest directed daily use")
            qualifier = {">=": "at least ", ">": "more than "}.get(ceiling.get("quantity_operator"), "")
            return (f"The label provides {qualifier}{_num(ceiling.get('amount_mg_day')):g} mg of caffeine a day {use}, "
                    f"above the {_num(ceiling.get('exceeds_above_mg_day')):.0f} mg/day that FDA describes as generally "
                    f"not associated with negative effects for most adults, {outcome}.")
        if ceiling.get("frequency_defaulted"):
            exposure = (f"The label gives no daily amount; at one serving a day {nutrient} exceeds its "
                        "established upper limit")
        elif ceiling.get("minimum_exceeds"):
            exposure = (f"Even the lowest directed daily use of {nutrient} exceeds its established "
                        "upper limit")
        else:
            exposure = (f"The higher directed daily amounts of {nutrient} exceed its established "
                        "upper limit")
        return f"{exposure}, {outcome}."
    flags = evaluation.get("flags")
    if isinstance(flags, list) and flags:
        is_actionable = any(
            isinstance(flag, dict)
            and flag.get("state") == "confirmed_over_threshold"
            for flag in flags
        )
    else:
        state_counts = evaluation.get("state_counts")
        is_actionable = (
            isinstance(state_counts, dict)
            and _num(state_counts.get("confirmed_over_threshold")) > 0
        )
    if not is_actionable:
        # An unresolved check is not an excess, but it is still a dose-safety
        # finding; Dose owns saying so (the sixth pillar only names concerns
        # it actually deducts).
        state_counts = evaluation.get("state_counts")
        if isinstance(state_counts, dict) and _num(state_counts.get("material_but_unresolved")) > 0:
            unresolved = dose_safety_consumer_explanation({"material_but_unresolved": 1}) or ""
            return unresolved[:1].upper() + unresolved[1:] + "."
        return None
    return (
        "At the label's maximum daily use, one or more nutrients exceed "
        "established safety limits."
    )


def _reason_evidence(band: str) -> str:
    return {
        "high": "Backed by strong human research.",
        "mid": "Some human research supports these ingredients.",
        "low": "Limited human evidence for these ingredients.",
    }[band]


def _reason_transparency(band: str) -> str:
    return {
        "high": "Fully transparent label — every amount is disclosed.",
        "mid": "Mostly transparent, but some amounts aren't fully disclosed.",
        "low": "Key amounts are hidden in a proprietary blend.",
    }[band]


def _probiotic_transparency_reason(dim: Dict[str, Any], fallback: str) -> str:
    components = dim.get("components") if isinstance(dim, dict) else None
    if not isinstance(components, dict):
        return fallback
    named = _num(components.get("strain_identities_named"))
    per_strain = _num(components.get("per_strain_cfu_on_label"))
    if _num(components.get("aggregate_native_afu_disclosure")) > 0:
        return "The formula's AFU amounts and strain identities are disclosed; individual strain amounts are not."
    aggregate = _num(components.get("aggregate_cfu_disclosure_proxy"))
    if named >= 8.0 and per_strain <= 0.0 and aggregate > 0.0:
        return (
            "All strains are named and total CFU is disclosed, but amounts "
            "for each strain are not."
        )
    if named >= 8.0 and per_strain <= 0.0:
        return "All strains are named, but their CFU amounts are not disclosed."
    if named > 0.0 and per_strain < 7.0:
        return "Some strain identities or CFU amounts are not fully disclosed."
    return fallback


# Omega Transparency items in rubric order; a missing component was not disclosed.
# Only what the pillar still SCORES belongs here. Oxidation testing was retired
# from Transparency on 2026-09-18 (lot-level testing belongs to Verification):
# naming it kept telling every omega label that oxidation testing was missing
# from a pillar that no longer charges for it, and made the "all disclosed"
# sentence unreachable, since a retired component can never be credited.
_OMEGA_DISCLOSURE_ITEMS = (
    ("epa_or_dha_disclosed", "EPA/DHA amounts"),
    ("source_disclosed", "the marine or algal source"),
    ("form_disclosed", "the molecular form"),
)


def _join_items(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _omega_transparency_reason(dim: Dict[str, Any], fallback: str) -> str:
    """Name the disclosures the omega Transparency score credited and withheld."""
    components = dim.get("components") if isinstance(dim, dict) else None
    if not isinstance(components, dict):
        return fallback
    shown = [label for key, label in _OMEGA_DISCLOSURE_ITEMS if _num(components.get(key)) > 0]
    missing = [label for key, label in _OMEGA_DISCLOSURE_ITEMS if _num(components.get(key)) <= 0]
    if not missing:
        reason = "EPA/DHA amounts, the molecular form and the source are all disclosed."
    elif not shown:
        reason = f"{_join_items(missing)[0].upper()}{_join_items(missing)[1:]} are not disclosed."
    else:
        head = _join_items(shown)
        reason = (f"{head[0].upper()}{head[1:]} {'is' if len(shown) == 1 else 'are'} disclosed; "
                  f"{_join_items(missing)} {'is' if len(missing) == 1 else 'are'} not.")
    if _num((dim.get("penalties") or {}).get("B5_proprietary_blend_opacity")) < 0:
        reason = reason[:-1] + ", and a proprietary blend hides individual amounts."
    return reason


# Generic dispatcher for any pillar that routes through the plain linear builders
# (only ``transparency`` does today). Keeps a jargon-free fallback so a future
# reconfigured pillar can never leak internal copy to consumers.
_BANDED_REASON = {
    "formulation": _reason_formulation,
    "dose": _reason_dose,
    "evidence": _reason_evidence,
    "transparency": _reason_transparency,
}


def _reason_generic(name: str, band: str) -> str:
    fn = _BANDED_REASON.get(name)
    if fn is not None:
        return fn(band)
    label = name.replace("_", " ")
    return {
        "high": f"Strong {label}.",
        "mid": f"Moderate {label}.",
        "low": f"Limited {label}.",
    }[band]


def shipped_whole_score(score: float) -> int:
    """The whole number the catalog ships and the app shows, from the scorer's
    one-decimal total. Round half up, exactly as build_final_db stores it.

    The tier must be a function of THIS number, not of the decimal total:
    a 69.6 ships as 70, and a 70 that reads "Weak" beside an "Acceptable"
    band starting at 70 is a contradiction the user sees on the hero card.
    """
    return int(math.floor(float(score) + 0.5))


def _tier(score: float) -> str:
    bands = _config()["tiers"]  # ordered high→low min
    for band in bands:
        if score >= band["min"]:
            return band["name"]
    return bands[-1]["name"]


def _manuf_violation_split(module_bd: Dict[str, Any]) -> Dict[str, float]:
    """PR3: route a maker's violation deduction into ONE pillar by type.

    The raw ``manufacturer_violations`` deduction lives in the raw score but in NO
    pillar, so the public quality score is currently BLIND to maker violations (a
    product with an FDA violation scores identical to a clean one). Split it:
      - Class I / critical recall in 3y (``class_i_count_3y`` > 0) = safety/contamination
        → the SAFETY pillar absorbs the deduction.
      - otherwise (GMP / labeling / quality-system) → the VERIFICATION pillar.
    Magnitude = the raw deduction itself (same /100 scale), so nothing is invented.
    B7 (overdose) is NOT here — it already lowers the dose pillar."""
    mv = module_bd.get("manufacturer_violations") or {}
    score = _num(mv.get("score"))  # negative deduction or 0
    if score >= 0:
        return {"safety": 0.0, "verification": 0.0}
    penalty = abs(score)
    class_i = _num((mv.get("metadata") or {}).get("class_i_count_3y"))
    if class_i > 0:
        return {"safety": penalty, "verification": 0.0}
    return {"safety": 0.0, "verification": penalty}


def _pillar_from_dim(name: str, dim: Dict[str, Any], weight: float, src: str) -> Dict[str, Any]:
    score = _num(dim.get("score"))
    mx = _num(dim.get("max"))
    val = round((score / mx) * weight, 1) if mx else 0.0
    val = max(0.0, min(float(weight), val))
    reason = _reason_generic(name, _band(val, weight))
    if name == "transparency":
        metadata = dim.get("metadata") or {}
        count = _num(metadata.get("panel_active_count"))
        # Read the same source facts shown below the headline. Opacity penalties
        # may be waived or consolidated without disclosing child amounts.
        blend_facts = _proprietary_blend_facts(dim)
        hidden_fact = next((fact for fact in blend_facts
                            if fact["id"] == "undisclosed_ingredient_amount_count"), None)
        # A charged blend is always named, even when no member rows were captured
        # to count: B5 alone owns opacity, so the band can no longer hide it.
        blends_hide = (
            (hidden_fact is not None and _num(hidden_fact["value_display"]) > 0)
            or _num((dim.get("penalties") or {}).get("B5_proprietary_blend_opacity")) < 0
        )
        if count > 0:
            panel_full = (
                _num(metadata.get("panel_named_count"), -1) == count
                and _num(metadata.get("panel_dose_count"), -1) == count
            )
            if panel_full and blends_hide:
                reason = ("Amounts outside the proprietary blends are disclosed, but the blends "
                          "hide their individual ingredient amounts.")
            elif panel_full:
                reason = "Active ingredient identities and amounts are fully disclosed."
            elif blends_hide:
                reason = ("Not all active ingredient identities or individual amounts are disclosed, "
                          "and proprietary blends hide their individual ingredient amounts.")
            else:
                reason = "Not all active ingredient identities or individual amounts are disclosed."
        elif (
            blends_hide
            and _band(val, weight) == "high"
        ):
            reason = (
                "Most amounts are disclosed, but ingredients in a proprietary "
                "blend are listed without their individual amounts."
            )
        elif (
            hidden_fact is None
            and "PROPRIETARY_BLEND_PRESENT" in (metadata.get("flags") or [])
            and _band(val, weight) == "high"
        ):
            reason = "The label includes a proprietary blend."
        elif not blends_hide:
            disclosure = metadata.get("complete_active_disclosure") or {}
            incomplete = disclosure.get("incomplete_rows") or []
            if incomplete and all(
                row.get("blockers") == ["parent_total_row"] for row in incomplete
            ):
                reason = (
                    "The label includes an ingredient total; complete "
                    "individual-amount disclosure was not verified."
                )
            elif (
                reason == _reason_transparency("low")
                and "PROPRIETARY_BLEND_PRESENT" not in (metadata.get("flags") or [])
            ):
                # The low-band sentence blames a blend; say what actually lowered it.
                penalties = dim.get("penalties") or {}
                if _num(penalties.get("B6_marketing_claims")) < 0:
                    reason = "The label makes disease or marketing claims, which lowers transparency."
                elif _num(penalties.get("B2_false_allergen_free_claim")) < 0:
                    reason = "A free-from claim on the label conflicts with its ingredients."
                else:
                    reason = "Not all active ingredient identities or individual amounts are disclosed."
    if name == "transparency" and (dim.get("metadata") or {}).get("active_identity_complete") is False:
        # V4.1 Step 4: the disclosure base needs every active identified.
        reason = ("Not every active ingredient's identity could be confirmed, so the label "
                  "earns no base disclosure credit. " + reason)
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": {"source_dim": src, "raw_score": score, "raw_max": mx},
    }


def _pillar_from_bonuses(name: str, module_bd: Dict[str, Any],
                         sources: List[str], weight: float) -> Dict[str, Any]:
    total_score = 0.0
    total_max = 0.0
    parts: Dict[str, float] = {}
    for key in sources:
        b = module_bd.get(key) or {}
        total_score += _num(b.get("score"))
        total_max += _num(b.get("max"))
        parts[key] = _num(b.get("score"))
    val = round((total_score / total_max) * weight, 1) if total_max else 0.0
    val = max(0.0, min(float(weight), val))
    return {
        "score": val,
        "max": weight,
        "reason": _reason_generic(name, _band(val, weight)),
        "components": parts,
    }


def _clean_label_penalty(hits: Any, cfg: Dict[str, Any]) -> tuple[float, List[Dict[str, Any]]]:
    """Graduated clean-label additive penalty + per-hit enrichment.

    penalty = penalty_base (per-additive, from clean_label_policy.json; falls
    back to config tier_base) × role_multiplier[role]. Summed across flagged
    additives and clamped to the per-product cap. Pure function of the gate's
    clean_label_hits + config. Returns (total_penalty, enriched_hits) where each
    enriched hit carries `penalty_applied` (its own pre-cap contribution) for the
    flag. The raw v4 score is never touched by this.
    """
    sub = cfg.get("clean_label_subscale") or {}
    if not sub or not isinstance(hits, list) or not hits:
        return 0.0, []
    role_mult = sub.get("role_multiplier") or {}
    tier_base = sub.get("tier_base") or {}
    cap = _num(sub.get("max_total_penalty"))
    enriched: List[Dict[str, Any]] = []
    running = 0.0
    for h in hits:
        if not isinstance(h, dict):
            continue
        base = h.get("penalty_base")
        if base is None:
            base = tier_base.get(str(h.get("tier") or "").lower())
        mult = role_mult.get(str(h.get("role") or "").lower())
        if mult is None:
            mult = 0.5  # conservative default for an unmapped role
        pen = round(_num(base) * _num(mult), 1)
        enriched.append({**h, "penalty_applied": pen})
        running += pen
    total = round(min(running, cap) if cap else running, 1)
    return total, enriched


def _build_clean_label_flags(enriched_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Public Flutter-facing clean_label_flags_v4 (the 'inform' half). All fields are
    data-sourced from the resolved entry — no invented status strings."""
    flags: List[Dict[str, Any]] = []
    for h in enriched_hits:
        flags.append({
            "additive": h.get("name"),
            "standard_name": h.get("standard_name"),
            "role": h.get("role"),
            "tier": h.get("tier"),
            "consumer_note": h.get("consumer_note"),
            "status": h.get("status"),
            "penalty_applied": h.get("penalty_applied"),
            "matched_rule_id": h.get("matched_rule_id"),
            "policy_id": h.get("policy_id"),
            "jurisdiction": h.get("jurisdiction"),
            "jurisdiction_status": h.get("jurisdiction_status"),
            "policy_basis": h.get("policy_basis"),
            # Step 3b: clickable regulation citation (null when the entry has none).
            # Stable keys so Flutter can rely on the contract.
            "eu_status": h.get("eu_status"),
            "regulation_citation": h.get("regulation_citation"),
            "regulation_url": h.get("regulation_url"),
        })
    return flags


def _formula_check_charge(module_bd: Dict[str, Any], cfg: Dict[str, Any]) -> tuple[float, bool]:
    """The formula-checks pillar's one charge for additive and sugar findings.

    V4.1 Step 4: Formulation no longer subtracts these findings; this pillar
    charges them once, low-severity entries included, within its shared budget
    (``safety_hygiene_subscale.additive_or_sweetener_max_penalty``). Returns the
    charge and whether any charged finding is above low severity.
    """
    formulation = ((module_bd.get("dimensions") or {}).get("formulation") or {})
    metadata = formulation.get("metadata") or {}
    checks = metadata.get("formula_checks") or {}
    raw = sum(max(0.0, _num(value)) for value in checks.values())
    if raw <= 0:
        return 0.0, False
    cap = float(cfg["safety_hygiene_subscale"]["additive_or_sweetener_max_penalty"])
    details = [d for d in metadata.get("inactive_penalty_details") or [] if isinstance(d, dict)]
    low_only = (
        _num(checks.get("B1_dietary_sugar")) <= 0
        and bool(details)
        and all(str(d.get("penalty_tier") or "").lower() == "low" for d in details)
    )
    return round(min(raw, cap), 1), not low_only


def _dose_safety_state_counts(module_bd: Dict[str, Any]) -> Dict[str, Any]:
    dose = ((module_bd.get("dimensions") or {}).get("dose") or {})
    metadata = dose.get("metadata") or {}
    evaluation = metadata.get("B7_safety_evaluation") or {}
    counts = evaluation.get("state_counts")
    return dict(counts) if isinstance(counts, dict) else {}


_SAFETY_STATUS_COPY = {
    "banned": ("a banned ingredient", "banned ingredients"),
    "recalled": ("a recalled ingredient", "recalled ingredients"),
    "high_risk": ("a high-risk ingredient", "high-risk ingredients"),
    "watchlist": ("a watchlisted ingredient", "watchlisted ingredients"),
}


def _safety_base_cause(base: Dict[str, Any]) -> Optional[str]:
    """Name what zeroed the safety base, from the drivers the base recorded."""
    metadata = base.get("metadata") or {}
    if metadata.get("not_evaluable_reason"):
        return None
    drivers = [d for d in metadata.get("drivers") or [] if isinstance(d, dict)]
    if not drivers:
        return "a banned, recalled, or watchlisted ingredient"
    phrases = []
    for status, (one, many) in _SAFETY_STATUS_COPY.items():
        names = [str(d["name"]) for d in drivers if d.get("status") == status and d.get("name")]
        if names:
            phrases.append(f"{many if len(names) > 1 else one} ({', '.join(names)})")
        elif any(d.get("status") == status for d in drivers):
            phrases.append(one)
    return " and ".join(phrases) or "a banned, recalled, or watchlisted ingredient"


def _pillar_safety_hygiene(module_bd: Dict[str, Any], weight: float,
                           cfg: Dict[str, Any],
                           clean_label_penalty: float = 0.0,
                           catalog_caution: bool = False) -> Dict[str, Any]:
    """Product-level safety pillar (/10). Clean base (no banned/recalled/watchlist) maps
    to full credit; banned/recalled/watchlist present already zeroes the raw base. PR3:
    a Class I (critical) manufacturer recall deducts the raw violation magnitude here (the
    safety/contamination half of the violation split). Step 3a: a clean-label additive
    (titanium dioxide / E171) deducts a SMALL graduated penalty here (inform + penalize,
    no forced CAUTION). V4.1 Step 4: this pillar is the one numerical owner of
    additive and dietary-sugar findings (formulation metadata ``formula_checks``,
    low severity included, worded as quality) within its shared budget, and only
    a confirmed high-risk or watchlist match zeroes its base. Dose owns the B7 deduction once; confirmed
    or unresolved dose findings remain visible here without another deduction."""
    base = module_bd.get("safety_hygiene_base") or {}
    bscore = _num(base.get("score"))
    bmax = _num(base.get("max"))
    clean = round((bscore / bmax) * weight, 1) if bmax else 0.0
    clean = max(0.0, min(float(weight), clean))
    safety_pen = _manuf_violation_split(module_bd)["safety"]
    cl_pen = max(0.0, _num(clean_label_penalty))
    additive_pen, additive_concern = _formula_check_charge(module_bd, cfg)
    dose_safety_state_counts = _dose_safety_state_counts(module_bd)
    dose_safety_explanation = dose_safety_consumer_explanation(
        dose_safety_state_counts
    )
    val = round(max(0.0, min(float(weight), clean - safety_pen - cl_pen - additive_pen)), 1)
    deductions = []
    # The base failure removes the most points, so its cause always leads.
    base_cause = _safety_base_cause(base) if bmax > 0 and bscore <= 0 else None
    if base_cause:
        deductions.append(f"it contains {base_cause}")
    if safety_pen > 0:
        deductions.append("the maker had a serious product recall")
    if cl_pen > 0:
        deductions.append("it contains a restricted additive")
    if additive_pen > 0 and additive_concern:
        deductions.append("it contains additive or sweetener/form-factor concerns")
    # Dose owns the B7 deduction, so a recorded dose-safety finding is always
    # worded as not deducted here, whether or not this pillar deducts.
    # The reason is one sentence; a second finding becomes a fact. A dose-safety
    # finding not deducted here stays the consumer fact, so it remains visible.
    facts: List[Dict[str, Any]] = []
    not_deducted = ({"id": "dose_safety_not_deducted", "label": "Dose-safety finding",
                     "value_display": dose_safety_explanation[0].upper() + dose_safety_explanation[1:],
                     "audience": CONSUMER} if dose_safety_explanation else None)
    if deductions:
        # Plain-English join: "A and B" rather than a comma list.
        reason = "Safety concern: " + " and ".join(deductions) + "."
        if additive_pen > 0 and not additive_concern:
            facts.append(audit_fact("formula_check", "Formula check",
                                    "It also contains low-concern additives or sweeteners that lower formula quality."))
        if not_deducted:
            facts.append(not_deducted)
    elif additive_pen > 0:
        # Low-concern excipients are a formula-quality signal, never a safety claim.
        reason = ("Formula check: it contains low-concern additives or sweeteners that "
                  "lower formula quality.")
        if not_deducted:
            facts.append(not_deducted)
    elif dose_safety_explanation:
        # A recorded dose-safety finding stays visible here, worded so a full
        # score does not read as "no concern" or as this pillar's deduction.
        reason = "Not deducted here: " + dose_safety_explanation + "."
    elif catalog_caution:
        # An unconfirmed (likely/review) high-risk or watchlist match is not
        # charged here, so the sentence claims no more than "not confirmed".
        reason = ("These formula checks did not confirm a concern, but this product carries a "
                  "separate safety caution.")
    else:
        reason = ("No catalog-level formula concerns were found in the checks performed; "
                  "personal suitability was not assessed.")
    components = {"clean_base": clean, "class_i_recall_penalty": safety_pen}
    if cl_pen > 0:
        components["clean_label_penalty"] = cl_pen
    if additive_pen > 0:
        components["additive_or_sweetener_penalty"] = additive_pen
    if dose_safety_state_counts:
        components["dose_safety_state_counts"] = dose_safety_state_counts
    pillar = {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": components,
    }
    if facts:
        pillar["explanation"] = facts_block(facts)
    return pillar


def _archetype(module: Optional[str], module_bd: Dict[str, Any]) -> str:
    if module == "sports":
        subtype = str((module_bd.get("metadata") or {}).get("sports_subtype") or "").strip().lower()
        if subtype == "pre_workout":
            return "sports_pre_workout"
        if subtype == "protein":
            return "sports_protein"
        if subtype == "bcaa_eaa":
            return "sports_bcaa_eaa"
        return "sports_single"
    if module == "fiber_digestive":
        return "fiber_digestive"
    if module == "b_complex":
        return "b_complex"
    if module == "omega":
        return "omega"
    if module == "probiotic":
        return "probiotic"
    if module == "multi_or_prenatal":
        return "prenatal_multi"
    form = (module_bd.get("dimensions", {}) or {}).get("formulation") or {}
    meta = form.get("metadata") or {}
    immune_meta = meta.get("immune_support") or {}
    if (
        immune_meta.get("profile_applied")
        or immune_meta.get("design_audit_applied")
    ):
        return "immune_support"
    if meta.get("botanical_profile_applied") or meta.get("collagen_profile_applied"):
        return "generic_botanical_branded"
    return "generic_single_molecule"


def _pillar_formulation(dim: Dict[str, Any], weight: float, archetype: str,
                        cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Category-aware purpose-fit formulation. Normalize to the archetype's ACHIEVABLE
    form ceiling (single ingredients can't earn breadth components A2-A5), so a
    best-in-class form earns ~19-20 by being optimal, not by faking breadth. A cheap
    form (low raw formulation) still scores low — this discriminates within the
    archetype, it does not anchor on corpus best-in-class."""
    sub = cfg["formulation_subscale"]
    meta = dim.get("metadata") or {}
    profile = str(meta.get("formulation_profile") or "").strip()
    ref = (
        sub.get("profile_reference", {}).get(profile)
        or sub["archetype_reference"].get(archetype, sub["default_reference"])
    )
    score = _num(dim.get("score"))
    val = round(max(0.0, min(float(weight), (score / ref) * weight)), 1) if ref else 0.0
    reason = (
        _profile_formulation_reason(meta)
        or _route_formulation_reason(dim, _band(val, weight))
        or _reason_formulation(_band(val, weight))
    )
    assessed_count = meta.get("iqm_form_quality_assessed_count")
    if (
        type(assessed_count) is int and assessed_count == 0
        and not meta.get("botanical_profile_applied")
        and not meta.get("collagen_profile_applied")
    ):
        # An unrated form is unknown, not poor: the module's A1 already carries
        # the shared unrated neutral (generic_formulation.UNRATED_FORM_NEUTRAL).
        reason = "Ingredient-form quality has not been assessed for these ingredients."
    if archetype == "omega":
        reason = _omega_formulation_reason(dim, reason)
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": {
            "raw_formulation": score,
            "archetype": archetype,
            "formulation_profile": profile or None,
            "reference": ref,
        },
    }


#: What a zero MEANS, keyed by the canonical state generic_evidence and
#: probiotic_evidence already emit. This is not a second state machine - it is
#: the public meaning of the one that exists, and it lives beside the copy map
#: that is already keyed the same way.
#:
#: The invariant it enforces: a user-visible 0/20 must be a REVIEWED conclusion.
#: It may never mean "PharmaGuide has not done this review yet". Those were
#: indistinguishable in the public payload, so 3,995 products were reading as
#: "no clinical evidence" when the scorer had in fact recorded "not looked at".
EVIDENCE_REVIEWED_ZERO_STATES = frozenset({
    "evaluated_null",
    "evaluated_unfavorable",
    "no_qualifying_human_evidence",
})
EVIDENCE_COVERAGE_GAP_STATES = frozenset({
    "clinical_review_not_covered",
    "native_research_review_incomplete",
    "human_clinical_evidence_unestablished",
    "identity_material_unresolved",
    "literature_resolution_required",
})
EVIDENCE_APPLICABILITY_STATES = frozenset({
    "applicability_unestablished",
    "research_present_applicability_unestablished",
})
EVIDENCE_NOT_APPLICABLE_STATES = frozenset({
    "no_assessable_actives",
    "not_efficacy_relevant",
})
EVIDENCE_ASSESSED_STATES = frozenset({
    "evaluated_applicable",
    "evaluated_authority",
    "authority_supported",
    "evaluated_null",
    "evaluated_unfavorable",
    "no_qualifying_human_evidence",
})


def evidence_display_state(state: Optional[str]) -> str:
    """The one place that decides how an Evidence result may be PRESENTED.

    Returns exactly one of:
      assessed                    - a reviewed result, numeric or a reviewed zero
      not_yet_reviewed            - a coverage gap; must NOT render as 0/20
      applicability_unestablished - reviewed, but not applicable to this label
      not_applicable              - nothing on this label to assess

    Phase 5 doctrine: Assessment state is derived strictly from the canonical
    Evidence disposition and never sees the points. Points are an output of
    assessment, not proof that assessment occurred.
    """
    if state in EVIDENCE_COVERAGE_GAP_STATES:
        return "not_yet_reviewed"
    if state in EVIDENCE_APPLICABILITY_STATES:
        return "applicability_unestablished"
    if state in EVIDENCE_NOT_APPLICABLE_STATES:
        return "not_applicable"
    if state in EVIDENCE_ASSESSED_STATES:
        return "assessed"
    # An undeclared state is never presented as a finished review.
    return "not_yet_reviewed"


_EVIDENCE_ZERO_REASON = {
    "human_clinical_evidence_unestablished": (
        "Our review of human clinical evidence is incomplete; the recorded nonclinical or "
        "unresolved sources do not establish benefit; this is not a product-quality finding."
    ),
    "native_research_review_incomplete": (
        "Our strain-specific human clinical review is incomplete; no conclusion about benefit "
        "or product quality follows from this review gap."
    ),
    "clinical_review_not_covered": (
        "Clinical evidence review pending: we haven't finished reviewing the ingredients on this "
        "label yet, which does not mean they lack clinical evidence."
    ),
    "identity_material_unresolved": (
        "Active ingredient identity or material form requires further scientific clarification before evidence can be assessed."
    ),
    "applicability_unestablished": (
        "Available research has not established a match to this product's assessed ingredients and use."
    ),
    "evaluated_unfavorable": "Reviewed human research did not show benefit for these ingredients.",
    "evaluated_null": (
        "We reviewed the human research and it did not establish a clear benefit for these "
        "ingredients."
    ),
    "evaluated_authority": (
        "Established nutritional authority recognizes the physiological necessity of these essential nutrients."
    ),
    "no_qualifying_human_evidence": (
        "We reviewed the research but found no qualifying human clinical evidence of benefit applicable to this product."
    ),
    "no_assessable_actives": "No active ingredient on this label could be assessed for clinical evidence.",
}

#: Not every state carries its own sentence. One that does not must still never
#: fall through to the numeric band copy, which reads "Limited human evidence
#: for these ingredients." - a REVIEWED finding of weakness, and precisely the
#: claim a coverage gap or an applicability gap does not support. So a state
#: without its own copy borrows the canonical sentence for its DISPLAY class,
#: keyed off evidence_display_state rather than a second table.
#:
#: Latent today: no product in the corpus reaches a non-probiotic zero in one of
#: these states, so this changes no shipped explanation. It exists so the state
#: sets and the copy map cannot drift apart later without the contract test
#: noticing.
_EVIDENCE_ZERO_CLASS_FALLBACK = {
    "not_yet_reviewed": "clinical_review_not_covered",
    "applicability_unestablished": "applicability_unestablished",
    "not_applicable": "no_assessable_actives",
}


def _pillar_evidence(dim: Dict[str, Any], weight: float, archetype: str,
                     cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Category-aware evidence fit against reviewed engine/purpose ceilings.

    Generic evidence tops out at 18 by construction; category engines may have
    different limits (for example, omega explicitly supports 15 + 5 = 20).
    References must come from those contracts, never the current corpus maximum.
    A weak-evidence product remains low because normalization is proportional.
    """
    sub = cfg["evidence_subscale"]
    ref = sub["archetype_reference"].get(archetype, sub["default_reference"])
    score = _num(dim.get("score"))
    val = round(max(0.0, min(float(weight), (score / ref) * weight)), 1) if ref else 0.0
    reason = _reason_evidence(_band(val, weight))
    metadata = dim.get("metadata") or {}
    # Only claim the floor drove the credit when it actually did. A computed but
    # shadowed floor (the pipeline already exceeded it) must keep the normal
    # pipeline explanation, and equality is not floor-driven either. The verdict
    # comes from generic_evidence, which applies the floor — this does not
    # recompute it.
    if metadata.get("primary_evidence_floor_decisive"):
        reason = "Evidence credit is driven by the primary ingredient, not a trial of the whole formula."
    facts: List[Dict[str, Any]] = []
    if "evidence_family_certainty" in (dim.get("components") or {}):
        parts = dim["components"]
        reason = "Evidence credit reflects reviewed research for the assessed purpose and population only."
        facts.append(audit_fact(
            "evidence_research_breakdown", "Research assessment",
            f"Research certainty {parts.get('evidence_family_certainty', 0):g}/10; "
            f"product applicability {parts.get('product_applicability', 0):g}/6; "
            f"independent confirmation {parts.get('independent_replication_consistency', parts.get('independent_replication', 0)):g}/4. "
            "Findings are specific to the assessed purpose and population."))
        if metadata.get("notes"):
            facts.append(audit_fact("evidence_strongest_family", "Strongest research family", metadata["notes"]))
    if val == 0:
        state = metadata.get("evidence_result_state") or (
            metadata.get("generic_evidence_metadata") or {}).get("evidence_result_state")
        zero_copy = _EVIDENCE_ZERO_REASON.get(state)
        if archetype == "probiotic" and state == "evaluated_unfavorable":
            zero_copy = "Reviewed research is unfavorable for the assessed outcome; this is distinct from missing research."
        if state == "evaluated_authority":
            zero_copy = ("These ingredients were reviewed against established nutritional authority, "
                         "which earned no Evidence points for this product.")
        if archetype == "probiotic" and state == "applicability_unestablished":
            zero_copy = ("Our reviewed evidence does not establish probiotic benefit for this "
                         "product's assessed preparation, purpose and population; this is not "
                         "a product-quality finding.")
        if archetype == "probiotic" and state == "research_present_applicability_unestablished":
            zero_copy = ("Research involving these microorganisms is recorded, but its applicability "
                         "to this product's preparation, purpose and population is not established.")
        if zero_copy is None:
            zero_copy = _EVIDENCE_ZERO_REASON.get(
                _EVIDENCE_ZERO_CLASS_FALLBACK.get(
                    evidence_display_state(state)
                )
            )
        reason = zero_copy or reason

    # Carry the canonical state and its public display meaning onto the pillar so
    # the export and the UI branch on what the SCORER decided, instead of
    # re-deriving it from a number that cannot tell the two kinds of zero apart.
    result_state = metadata.get("evidence_result_state") or (
        metadata.get("generic_evidence_metadata") or {}).get("evidence_result_state")
    if result_state == "evaluated_authority" and val > 0:
        # Result-state ownership outranks generic floor copy: when established
        # nutrition authority set the Evidence result, say so. A zero keeps its
        # own sentence: authority cannot be credited with points never awarded.
        reason = _EVIDENCE_ZERO_REASON["evaluated_authority"]
    if val > 0 and evidence_display_state(result_state) == "not_yet_reviewed":
        # Credit already earned cannot finish the assessment while other
        # research on the label is still under review.
        reason = ("Some research on this label earned credit, but our review of the rest "
                  "is still open, so this assessment is not finished.")
    pillar = {
        "score": val,
        "max": weight,
        "reason": reason,
        "evidence_result_state": result_state,
        "display_state": evidence_display_state(result_state),
        "components": {"raw_evidence": score, "archetype": archetype, "reference": ref},
    }
    if facts:
        pillar["explanation"] = facts_block(facts)
    return pillar


def _dose_reference(dim: Dict[str, Any], archetype: str, sub: Dict[str, Any]) -> float:
    """The attainable Dose maximum for this product (V4.1 Step 4).

    The prenatal DHA complement has its existing route reference. Sports
    primaries use the common reference after composition credit retirement.
    """
    ref = sub["archetype_reference"].get(archetype, sub["default_reference"])
    variants = sub.get("assessed_component_reference") or {}
    components = dim.get("components") or {}
    metadata = dim.get("metadata") or {}
    if metadata.get("dose_aggregation") == "co_primary_average":
        # Each primary already uses its own assessed-component reference.
        return ref
    if archetype == "prenatal_multi" and str(metadata.get("critical_nutrient_mode") or "").startswith("prenatal"):
        return float(variants.get("prenatal_complement_assessed", ref))
    return ref


def _pillar_dose(dim: Dict[str, Any], weight: float, archetype: str,
                 cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Category-aware purpose-fit dose. Normalize to the archetype's APPROPRIATE-dose
    ceiling (a single nutrient/botanical in its clinical window caps ~22). Megadose-safe:
    an overdosed product already has low raw dose (overdose half-credit), a sub-clinical
    one is proportional-low — normalizing only lifts appropriately-dosed products, never
    rewards excess."""
    ref = _dose_reference(dim, archetype, cfg["dose_subscale"])
    score = _num(dim.get("score"))
    adequacy = round(max(0.0, min(float(weight), (score / ref) * weight)), 1) if ref else 0.0
    # Dose V4.1 §2.4: the strongest confirmed exceedance caps Dose once, after
    # aggregation and normalization; a ceiling never raises a lower score.
    ceiling = _dose_ceiling(dim)
    val = adequacy
    if ceiling is not None:
        val = (round(max(0.0, adequacy - _num(ceiling["deduction_public"])), 1)
               if ceiling.get("deduction_public") is not None
               else min(adequacy, _num(ceiling.get("cap_public"))))
    over_limit_reason = _over_limit_dose_reason(dim)
    reason = over_limit_reason
    if reason is None:
        reason = _undisclosed_component_dose_reason(dim)
    if reason is None:
        reason = _unassessed_primary_dose_reason(dim)
    if reason is None:
        reason = _reason_dose(_band(val, weight))
    if archetype == "omega" and over_limit_reason is None:
        reference = (dim.get("metadata") or {}).get("adequacy_reference") or {}
        target_mg = reference.get("target_mg_day")
        if reference.get("purpose") == "ordinary_adult" and isinstance(target_mg, (int, float)):
            reason = f"EPA + DHA at minimum directed daily use is compared with a {target_mg:g} mg adult nutritional reference contribution; more earns no additional Dose credit."
        elif reference.get("purpose") == "prenatal_dha" and isinstance(target_mg, (int, float)):
            reason = f"DHA at minimum directed daily use is compared with a {target_mg:g} mg additional-DHA reference contribution; this does not assess complete pregnancy nutrition."
    if archetype == "probiotic" and over_limit_reason is None:
        reason = _probiotic_dose_reason(dim, reason)
    components = {"raw_dose": score, "archetype": archetype, "reference": ref}
    if ceiling is not None:
        components["adequacy_before_safety"] = adequacy
        if ceiling.get("deduction_public") is not None:
            components["safety_deduction"] = _num(ceiling["deduction_public"])
        else:
            components["safety_ceiling"] = _num(ceiling.get("cap_public"))
    facts = _probiotic_dose_facts(dim) if archetype == "probiotic" and over_limit_reason is None else []
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": components,
        **({"explanation": facts_block(facts)} if facts else {}),
    }


def _pillar_verification(module_bd: Dict[str, Any], weight: float,
                         cfg: Dict[str, Any],
                         assessment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Verification / quality pillar (/15). Hard third-party signals SATURATE the
    cap (over-provisioned, clamps) so a subset maxes it. Self-asserted cGMP is table
    stakes. FAIL OPEN: no verification data = unknown → neutral baseline (not 0).
    1.3.0 orders evidence tiers so more independent evidence never scores lower:
    unknown 6 < claim/brand <= 8 < manufacturing <= 10 < product-level >= 11."""
    sub = cfg["verification_subscale"]
    cap = sub["cap"]
    vb_payload = module_bd.get("verification_bonus") or {}
    vb = vb_payload.get("components") or {}
    trust_meta = ((vb_payload.get("metadata") or {}).get("trust_metadata") or {})
    mt = (module_bd.get("manufacturer_trust") or {}).get("components") or {}
    b4a = _component_num(vb, "B4a_verified_certifications", "b4a_verified_certifications")
    b4b = _component_num(vb, "B4b_gmp", "b4b_gmp")
    b4c = _component_num(vb, "B4c_batch_traceability", "b4c_batch_traceability")
    b4d = _component_num(vb, "B4d_brand_testing_posture", "b4d_brand_testing_posture")
    scored_scopes = _verification_scope_counts(trust_meta)
    has_registry_cert = (
        _num(scored_scopes.get("sku")) > 0
        or _num(scored_scopes.get("product_line")) > 0
    )
    has_label_asserted_cert = _num(scored_scopes.get("label_asserted_product")) > 0
    unscored_scopes = trust_meta.get("verified_unscored_scope_counts") or {}
    brand_only_count = int(_num(unscored_scopes.get("brand_only")))

    cert = 0.0
    if has_registry_cert:
        for tier in sub["cert_tiers"]:  # ordered high→low
            if b4a >= tier["min_b4a"]:
                cert = tier["points"]
                break
    elif has_label_asserted_cert:
        cert = _num(sub.get("label_asserted_cert_points"))
    coa_batch = round(min(sub["coa_batch_max"], (b4c / 2.0) * sub["coa_batch_max"]), 2) if b4c else 0.0
    # Every GMP flag the enricher sets is matched from label text (self-asserted
    # table stakes). GMP only counts when a verified product cert implies an
    # audited facility or exact-matched manufacturer evidence names one.
    # GMP counts only on a basis decided by scoring_v4.cert_evidence (generic
    # trust emits it at top level, omega trust under "b4b"). The app's GMP badge
    # renders this decision; nothing re-derives GMP from label wording.
    from scoring_v4.cert_evidence import AUDITED_GMP_BASES
    reported_basis = trust_meta.get("gmp_basis") or (trust_meta.get("b4b") or {}).get("gmp_basis")
    gmp = sub["gmp_certified_points"] if (reported_basis in AUDITED_GMP_BASES and b4b >= 4.0) else 0.0
    gmp_basis = reported_basis if gmp > 0 else None
    testing = sub["brand_testing_points"] if b4d > 0 else 0.0
    # PR2.1: a verified brand/facility scoped cert is a real third-party
    # verification signal, but weaker than sku/product_line certification and
    # not evidence for this SKU. It never stacks on a product-level registry cert.
    brand_only_cert = (
        _num(sub.get("brand_only_cert_points"))
        if brand_only_count > 0 and not has_registry_cert
        else 0.0
    )
    # Manufacturer reputation is brand-level context; manufacturing region is not
    # verification and no longer counts. Mid-tier reputation is derived only
    # from verified certifications or audited GMP, which cert / gmp already
    # score, so it is not counted a second time here.
    mt_source = ((module_bd.get("manufacturer_trust") or {}).get("metadata") or {}).get("D1_source")
    reputation = (
        0.0
        if mt_source == "mid_tier_verified_evidence"
        else min(sub["reputation_cap"], _num(mt.get("D1_manufacturer_reputation")))
    )

    # 1.3.0 evidence tiers: more independent evidence can never score lower than
    # less. Unknown sits at the neutral baseline; claims and brand context can
    # add a little; manufacturing verification more; product-level verification
    # (a registry-backed product cert) always outranks every lower tier.
    # B4c is label/rules-derived traceability (even a QR code can set it).
    # It is not an independent laboratory verification of this product.
    product_verified = has_registry_cert
    manufacturing_verified = gmp > 0 or brand_only_cert > 0
    claim_or_brand = cert > 0 or testing > 0 or reputation > 0 or coa_batch > 0
    base = sub["neutral_baseline"] + cert + coa_batch + gmp + testing + brand_only_cert + reputation
    ceilings = sub["tier_ceilings"]
    if product_verified:
        tier = "product"
        total = max(sub["product_level_floor"], base)
    elif manufacturing_verified:
        tier = "manufacturing"
        total = min(ceilings["manufacturing"], base)
    elif claim_or_brand:
        tier = "claim_or_brand"
        total = min(ceilings["claim_or_brand"], base)
    else:
        tier = "unknown"
        total = sub["neutral_baseline"]
    fail_open = tier == "unknown"

    signals = []
    if has_registry_cert:
        signals.append("third-party certified")
    elif has_label_asserted_cert:
        signals.append("label claims third-party certification")
    if coa_batch > 0:
        signals.append("label provides COA or batch-lookup information")
    if brand_only_cert > 0:
        signals.append("holds a brand/facility certification verified by a third party")
    if gmp > 0:
        signals.append(
            "manufacturer is listed in an audited GMP facility registry"
            if gmp_basis == "manufacturer_facility"
            else "made in an audited GMP facility"
        )
    if testing > 0:
        signals.append("does its own purity testing")
    verification_facts: List[Dict[str, Any]] = []
    if tier == "product":
        reason = "Independently verified — " + ", ".join(signals) + "."
    elif tier == "manufacturing":
        reason = "Manufacturing verified; no independent product testing verified on file — " + ", ".join(signals) + "."
    elif tier == "claim_or_brand":
        detail = ", ".join(signals) if signals else "established manufacturer"
        reason = "Quality signals on file, not independently verified — " + detail + "."
    else:
        # Missing independent verification is not a failed product test.
        # Keep baseline arithmetic in the existing audit-only fact below.
        assessment = assessment if isinstance(assessment, dict) else {}
        if assessment.get("state") == "not_evaluated" or assessment.get("readiness") == "incomplete":
            reason = "Verification assessment is incomplete."
        elif (assessment.get("state") == "verified_absent"
              and assessment.get("readiness") == "complete"
              and assessment.get("reason_code") == "registry_evaluated_no_match"
              and _num(assessment.get("registry_source_count")) > 0
              and not assessment.get("migration_inference")):
            # This is the existing collector's completed registry finding,
            # not a claim that all independent test reports were searched.
            reason = "No third-party product certification found in the reviewed registries."
        else:
            # Missing or migration-inferred results cannot establish a search finding.
            reason = "Independent testing or certification: unconfirmed."
        verification_facts.append(audit_fact(
            "verification_neutral_baseline", "Neutral value",
            f"Neutral {_g(sub['neutral_baseline'])} of {_g(cap)}; "
            f"{_g(cap - sub['neutral_baseline'])} points need verified evidence."))

    # PR3: a quality-system (non-critical) manufacturer violation lowers verification.
    # Applied AFTER the positive cert logic + clamp so it composes with future baseline
    # changes (PR2.1) as an independent negative term.
    qs_pen = _manuf_violation_split(module_bd)["verification"]
    positive = min(cap, total)
    val = round(max(0.0, positive - qs_pen), 1)
    if qs_pen > 0:
        reason = reason[:-1] + "; the maker has an open quality-system violation."
    return {
        "score": val,
        "max": weight,
        "reason": reason,
        "components": {"cert": cert, "coa_batch": coa_batch, "gmp": gmp,
                       "gmp_basis": gmp_basis, "brand_testing": testing, "brand_only_cert": brand_only_cert,
                       "reputation": reputation, "tier": tier, "fail_open_neutral": fail_open,
                       "quality_system_violation_penalty": qs_pen},
        **({"explanation": facts_block(verification_facts)} if verification_facts else {}),
    }


def _verification_scope_counts(trust_meta: Dict[str, Any]) -> Dict[str, int]:
    """Return B4a scope counts across generic and omega trust metadata shapes."""
    direct = trust_meta.get("verified_scope_counts")
    if isinstance(direct, dict) and direct:
        return {str(key): int(_num(value)) for key, value in direct.items()}

    b4a = trust_meta.get("b4a")
    entries = (b4a or {}).get("B4a_scored_entries") if isinstance(b4a, dict) else None
    if not isinstance(entries, list):
        return {}

    counts: Dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "")
        if not scope:
            continue
        counts[scope] = counts.get(scope, 0) + 1
    return counts


# ── Score receipts (V4.1 accounting contract, AUDIT.md §8) ───────────────────
# A receipt itemizes a pillar the assembler already produced. It never changes
# a score: each receipt must replay the module result exactly and sum to the
# public pillar, or scoring fails closed (as an unregistered penalty does).

# Some modules round a dimension score to 0.01 (omega, probiotic) while their
# components keep four decimals, so a faithful replay can differ by up to 0.005.
_RECEIPT_TOLERANCE = 0.006
# Pillars round to 0.1 (residue ≤ 0.05); entries are reported to four decimals,
# which can add a few ten-thousandths to that residue.
_ROUNDING_BOUND = 0.0505
# A clamp or cap at least this large is itemized; smaller gaps are four-decimal
# component rounding and stay inside the rounding residue.
_ITEMIZE_THRESHOLD = 1e-4
_NEUTRAL_DOSE_BANDS = frozenset({"disclosed_no_reference", "blend_total_only", "primary_no_dose"})
_NEUTRAL_WINDOW_STATUSES = frozenset({
    "partial_credit_without_rda_proxy",
    "partial_credit_primary_active_unassessed",
})
_BONUS_WITHHOLDERS = frozenset({"disease_or_marketing_claim"})
#: Formulation components whose metadata names the share earned by unrated rows.
_UNRATED_NEUTRAL_SHARE = {
    "panel_form_quality": "panel_form_neutral_points",
    "b_form_quality": "b_form_neutral_points",
}


def _receipt_entry(entry_id: str, kind: str, source: str, raw: Optional[float],
                   points: float, **extra: Any) -> Dict[str, Any]:
    entry = {"id": entry_id, "kind": kind, "source": source}
    if raw is not None:
        entry["raw"] = round(float(raw), 4)
    entry["points"] = round(float(points), 4)
    entry.update({key: value for key, value in extra.items() if value is not None})
    return entry


def _receipt_mismatch(name: str, expected: Any, replayed: Any) -> RuntimeError:
    return RuntimeError(
        f"score receipt does not reconcile for {name}: scorer {expected!r}, receipt {replayed!r}")


def _dose_component_kind(key: str, kind: str, metadata: Dict[str, Any]) -> tuple[str, Optional[str]]:
    """Dose credit is neutral when it rests on a missing or unbenchmarked amount."""
    if key == "botanical_clinical_dose":
        band = metadata.get("botanical_dose_band")
        return ("neutral" if band in _NEUTRAL_DOSE_BANDS else kind), band
    if key == "collagen_clinical_dose":
        band = metadata.get("collagen_dose_band")
        return ("neutral" if band in _NEUTRAL_DOSE_BANDS else kind), band
    if key == "sports_primary_active_dose":
        labels = [str(e.get("assessment") or "") for e in metadata.get("dose_contributions") or []]
        if labels and all(label.endswith("_completed_no_general_benchmark") or label == "hidden_amount_neutral" for label in labels):
            return "neutral", "completed_no_general_benchmark"
    if key in {"fiber_effective_dose", "sleep_support_dose", "joint_support_dose"}:
        return "neutral", "completed_no_general_benchmark"
    if key == "supplemental_window_proxy":
        status = metadata.get("window_proxy_status")
        return ("neutral" if status in _NEUTRAL_WINDOW_STATUSES else kind), status
    return kind, None


def _profile_detail(metadata: Dict[str, Any]) -> Optional[tuple[str, Dict[str, Any]]]:
    for section, applied_key in (("botanical_formulation", "botanical_profile_applied"),
                                 ("collagen_formulation", "collagen_profile_applied")):
        detail = metadata.get(section)
        if metadata.get(applied_key) and isinstance(detail, dict):
            return section, detail
    return None


def _itemize_dimension(name: str, dim: Dict[str, Any]) -> tuple[List[tuple], float, float]:
    """Raw-scale items for one module dimension, its replay, and its no-deduction value.

    Items are (id, kind, source, raw, extra). The replay must equal the module's
    own score; the no-deduction value repeats the same bounds without penalties.
    """
    components = dim.get("components") or {}
    penalties = dim.get("penalties") or {}
    metadata = dim.get("metadata") or {}
    mx = _num(dim.get("max"))
    items: List[tuple] = []
    additive = 0.0
    deductions = 0.0
    evidence_floor: Optional[float] = None
    evidence_caps: List[tuple] = []
    for key, value in components.items():
        amount = _num(value)
        if name == "evidence" and key in EVIDENCE_FLOOR_KEYS:
            evidence_floor = amount
            continue
        if name == "evidence" and key in EVIDENCE_CAP_KEYS:
            evidence_caps.append((key, amount))
            continue
        profile = _profile_detail(metadata) if (name == "formulation" and key == "A1_bio_score") else None
        if profile is not None:
            # Nested detail replaces its aggregate; it is never added on top of it.
            section, detail = profile
            detail_sum = 0.0
            for sub_key, sub_value in detail.items():
                sub_amount = _num(sub_value)
                if sub_amount == 0:
                    continue
                items.append((sub_key, component_kind(section, sub_key), f"{section}.{sub_key}", sub_amount, {}))
                detail_sum += sub_amount
            bound = amount - detail_sum
            if abs(bound) > _ITEMIZE_THRESHOLD:
                items.append((f"{section}_bounds", "cap" if bound < 0 else "floor",
                              f"{section}.cap", bound, {}))
            additive += amount
            continue
        if amount == 0:
            continue
        neutral_key = _UNRATED_NEUTRAL_SHARE.get(key) if name == "formulation" else None
        neutral = _num(metadata.get(neutral_key)) if neutral_key else 0.0
        if neutral > _ITEMIZE_THRESHOLD:
            # Unrated rows keep the shared neutral; show it apart from earned quality.
            if amount - neutral > _ITEMIZE_THRESHOLD:
                items.append((key, "earned", f"{name}.{key}", amount - neutral, {}))
            items.append((f"{key}_unrated_neutral", "neutral", "generic_formulation.UNRATED_FORM_NEUTRAL",
                          min(neutral, amount), {}))
            additive += amount
            continue
        if (name == "formulation" and key == "A1_bio_score"
                and metadata.get("iqm_form_quality_assessed_count") == 0):
            items.append(("A1_unrated_neutral", "neutral", "generic_formulation.UNRATED_FORM_NEUTRAL", amount, {}))
            additive += amount
            continue
        kind = component_kind(name, key)
        basis = None
        if name == "dose":
            kind, basis = _dose_component_kind(key, kind, metadata)
        items.append((key, kind, f"{name}.{key}", amount, {"basis": basis}))
        additive += amount
    for key, value in penalties.items():
        amount = _num(value)
        if amount == 0:
            continue
        penalty_spec(key)
        items.append((key, "deduction", f"{name}.{key}", -abs(amount), {}))
        deductions -= abs(amount)

    if name == "transparency":
        disclosure = metadata.get("complete_active_disclosure") or {}
        withheld = [b for b in (disclosure.get("blockers") or []) if b in _BONUS_WITHHOLDERS]
        if ("complete_active_identity_dose_disclosure" in components and disclosure.get("qualifies") is False
                and withheld):
            items.append(("complete_active_identity_dose_disclosure", "disclosure",
                          "transparency.complete_active_identity_dose_disclosure", 0.0,
                          {"withheld_by": withheld}))

    score = dim.get("score")
    if score is None:
        return items, 0.0, 0.0

    if name == "evidence":
        running = additive + deductions
        if evidence_floor is not None and evidence_floor > running:
            items.append(("primary_evidence_floor", "floor", "evidence.primary_evidence_floor",
                          evidence_floor - running, {}))
            running = evidence_floor
        bounded = max(0.0, min(mx, running))
        if abs(bounded - running) > _ITEMIZE_THRESHOLD:
            items.append(("evidence_dimension_bounds", "cap" if bounded < running else "floor",
                          "evidence.max", bounded - running, {}))
        running = bounded
        for key, cap in evidence_caps:
            if running > cap:
                items.append((key, "cap", f"evidence.{key}", cap - running, {}))
                running = cap
        replay, without_deductions = running, running
    else:
        running = additive + deductions
        bounded = max(0.0, min(mx, running))
        if abs(bounded - running) > _ITEMIZE_THRESHOLD:
            items.append((f"{name}_dimension_bounds", "cap" if bounded < running else "floor",
                          f"{name}.max", bounded - running, {}))
        replay = bounded
        without_deductions = max(0.0, min(mx, additive))
        presence = metadata.get("presence_floor") if name == "formulation" else None
        if isinstance(presence, dict) and presence.get("applied"):
            target = _num(presence.get("target"))
            if replay < target:
                items.append(("presence_floor", "floor", "formulation_magnitudes.presence_floor",
                              target - replay, {}))
                replay = target
            if 0 < additive < target:
                without_deductions = max(without_deductions, target)
    if abs(replay - _num(score)) > _RECEIPT_TOLERANCE:
        raise _receipt_mismatch(f"{name} dimension", score, round(replay, 4))
    if abs(_num(score) - replay) > 1e-9:
        # The module rounded its dimension score coarser than its components;
        # the no-deduction value carries the same rounding so they stay comparable.
        offset = _num(score) - replay
        items.append(("module_rounding", "rounding", f"{name}.score", offset, {}))
        replay = _num(score)
        without_deductions = max(0.0, min(mx, without_deductions + offset))
    if deductions == 0:
        without_deductions = replay
    return items, replay, without_deductions


def _finish_receipt(pillar: Dict[str, Any], entries: List[Dict[str, Any]],
                    without_deductions_score: float) -> Dict[str, Any]:
    """Close a receipt: rounding residue, deductions and unawarded capacity."""
    score = _num(pillar.get("score"))
    residue = round(score - sum(entry["points"] for entry in entries), 4)
    if abs(residue) > _ROUNDING_BOUND:
        raise _receipt_mismatch("pillar", score, round(score - residue, 4))
    if residue:
        entries.append(_receipt_entry("rounding", "rounding", "pillar.round_0_1", None, residue))
    realized = round(score - without_deductions_score, 4)
    return {
        "entries": entries,
        "nominal_deductions": round(sum(e["points"] for e in entries if e["kind"] == "deduction"), 4),
        "realized_deductions": realized,
        "unawarded": round(_num(pillar.get("max")) - without_deductions_score, 4),
    }


def _normalized_receipt(name: str, pillar: Dict[str, Any], dim: Dict[str, Any],
                        weight: float, rebuild) -> Dict[str, Any]:
    """Receipt for a pillar computed as clip(raw / reference × weight)."""
    components = pillar.get("components") or {}
    reference = _num(components.get("raw_max") if name == "transparency" else components.get("reference"))
    factor = (float(weight) / reference) if reference else 0.0
    items, replay, without_deductions = _itemize_dimension(name, dim)
    # An incomplete dimension retains diagnostic peer assessments, but those
    # are not awarded points in the unfinished public pillar.
    entries = ([] if dim.get("score") is None else
               [_receipt_entry(item_id, kind, source, raw, raw * factor, **extra)
                for item_id, kind, source, raw, extra in items])
    if dim.get("score") is None:
        entries.append(_receipt_entry(f"{name}_not_evaluable", "neutral", f"{name}.score", None, 0.0))
    public = replay * factor
    clipped = max(0.0, min(float(weight), public))
    if abs(clipped - public) > 1e-9:
        entries.append(_receipt_entry(f"{name}_pillar_bounds", "cap" if clipped < public else "floor",
                                      f"pillars.{name}.weight", None, clipped - public))
    ceiling = components.get("safety_ceiling") if name == "dose" else None
    if ceiling is not None and clipped > _num(ceiling):
        entries.append(_receipt_entry("dose_safety_ceiling", "cap", "dose_safety_ceiling", None,
                                      _num(ceiling) - clipped))
    deduction = components.get("safety_deduction") if name == "dose" else None
    if deduction is not None:
        entries.append(_receipt_entry("dose_safety_ceiling", "deduction", "dose_safety_ceiling", None,
                                      -min(clipped, _num(deduction))))
    without_score = (round(max(0.0, min(float(weight), without_deductions * factor)), 1)
                     if deduction is not None else
                     _num(rebuild({**dim, "score": without_deductions})["score"]))
    return _finish_receipt(pillar, entries, without_score)


def _verification_receipt(pillar: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    sub = cfg["verification_subscale"]
    components = pillar.get("components") or {}
    baseline = _num(sub["neutral_baseline"])
    entries = [_receipt_entry("neutral_baseline", "neutral", "verification_subscale.neutral_baseline",
                              baseline, baseline)]
    running = baseline
    for key in ("cert", "coa_batch", "gmp", "brand_testing", "brand_only_cert", "reputation"):
        amount = _num(components.get(key))
        if amount:
            entries.append(_receipt_entry(key, "earned", f"verification.{key}", amount, amount))
            running += amount
    tier = components.get("tier")
    ceilings = sub["tier_ceilings"]
    if tier == "product" and running < _num(sub["product_level_floor"]):
        lift = _num(sub["product_level_floor"]) - running
        entries.append(_receipt_entry("product_level_floor", "floor", "verification_subscale.product_level_floor",
                                      None, lift))
        running += lift
    elif tier in ("manufacturing", "claim_or_brand") and running > _num(ceilings[tier]):
        cut = _num(ceilings[tier]) - running
        entries.append(_receipt_entry(f"{tier}_ceiling", "cap", f"verification_subscale.tier_ceilings.{tier}",
                                      None, cut))
        running += cut
    elif tier == "unknown" and abs(running - baseline) > 1e-9:
        raise _receipt_mismatch("verification tier", baseline, running)
    cap = _num(sub["cap"])
    if running > cap:
        entries.append(_receipt_entry("verification_cap", "cap", "verification_subscale.cap", None, cap - running))
        running = cap
    without_deductions = round(running, 1)
    violation = _num(components.get("quality_system_violation_penalty"))
    if violation:
        entries.append(_receipt_entry("quality_system_violation_penalty", "deduction",
                                      "manufacturer_violations.manufacturer_violation_deduction",
                                      -violation, -violation))
        if running - violation < 0:
            entries.append(_receipt_entry("verification_floor", "floor", "pillars.verification.min",
                                          None, violation - running))
    return _finish_receipt(pillar, entries, without_deductions)


def _safety_receipt(pillar: Dict[str, Any], weight: float) -> Dict[str, Any]:
    components = pillar.get("components") or {}
    clean = _num(components.get("clean_base"))
    entries = [_receipt_entry("catalog_screen", "neutral", "safety_hygiene_base", None, clean)]
    running = clean
    for key, source in (("class_i_recall_penalty", "manufacturer_violations.class_i"),
                        ("clean_label_penalty", "clean_label_subscale"),
                        ("additive_or_sweetener_penalty", "formulation.metadata.formula_checks")):
        amount = _num(components.get(key))
        if amount:
            entries.append(_receipt_entry(key, "deduction", source, -amount, -amount))
            running -= amount
    if running < 0:
        entries.append(_receipt_entry("safety_hygiene_floor", "floor", "pillars.safety_hygiene.min",
                                      None, -running))
    return _finish_receipt(pillar, entries, round(max(0.0, min(float(weight), clean)), 1))


def _attach_score_receipts(pillars: Dict[str, Any], module_bd: Dict[str, Any],
                           cfg: Dict[str, Any], archetype: str) -> Dict[str, Any]:
    """Attach a reconciling receipt to every scored pillar (in place).

    A legacy breakdown without itemized components gets no receipt at all,
    never a partial one.
    """
    dims = module_bd.get("dimensions") or {}
    names = ("formulation", "dose", "evidence", "transparency")
    if not all(isinstance((dims.get(name) or {}).get("components"), dict) for name in names):
        return pillars
    weights = {name: spec["weight"] for name, spec in cfg["pillars"].items()}
    rebuilders = {
        "formulation": lambda dim: _pillar_formulation(dim, weights["formulation"], archetype, cfg),
        "dose": lambda dim: _pillar_dose(dim, weights["dose"], archetype, cfg),
        "evidence": lambda dim: _pillar_evidence(dim, weights["evidence"], archetype, cfg),
        "transparency": lambda dim: _pillar_from_dim("transparency", dim, weights["transparency"], "transparency"),
    }
    for name in names:
        pillars[name]["receipt"] = _normalized_receipt(name, pillars[name], dims[name], weights[name],
                                                       rebuilders[name])
    pillars["verification"]["receipt"] = _verification_receipt(pillars["verification"], cfg)
    pillars["safety_hygiene"]["receipt"] = _safety_receipt(pillars["safety_hygiene"], weights["safety_hygiene"])
    return pillars


def _build_pillars(module_bd: Dict[str, Any], cfg: Dict[str, Any],
                   module: Optional[str],
                   clean_label_penalty: float = 0.0,
                   catalog_caution: bool = False,
                   verification_assessment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    dims = module_bd.get("dimensions") or {}
    archetype = _archetype(module, module_bd)
    pillars: Dict[str, Any] = {}
    for name, spec in cfg["pillars"].items():
        weight = spec["weight"]
        assembler = spec.get("assembler")
        if assembler == "verification":
            pillars[name] = _pillar_verification(module_bd, weight, cfg, verification_assessment)
        elif assembler == "safety_hygiene":
            pillars[name] = _pillar_safety_hygiene(module_bd, weight, cfg,
                                                   clean_label_penalty, catalog_caution)
        elif assembler == "formulation":
            pillars[name] = _pillar_formulation(dims.get("formulation") or {},
                                                weight, archetype, cfg)
        elif assembler == "dose":
            pillars[name] = _pillar_dose(dims.get("dose") or {}, weight, archetype, cfg)
        elif assembler == "evidence":
            pillars[name] = _pillar_evidence(dims.get("evidence") or {}, weight, archetype, cfg)
        elif "source_dim" in spec:
            pillars[name] = _pillar_from_dim(name, dims.get(spec["source_dim"]) or {},
                                             weight, spec["source_dim"])
        else:
            pillars[name] = _pillar_from_bonuses(name, module_bd,
                                                 spec["source_bonuses"], weight)
    if module == "probiotic" and "transparency" in pillars:
        transparency_dim = dims.get("transparency") or {}
        pillars["transparency"]["reason"] = _probiotic_transparency_reason(
            transparency_dim,
            pillars["transparency"]["reason"],
        )
    if module == "omega" and "transparency" in pillars:
        pillars["transparency"]["reason"] = _omega_transparency_reason(
            dims.get("transparency") or {},
            pillars["transparency"]["reason"],
        )
    return pillars


def assemble_quality_score(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add public six-pillar quality fields. Mutates & returns ``result``.
    ``raw_score_v4_100`` (raw) is never modified."""
    cfg = _config()
    raw = result.get("raw_score_v4_100")
    verdict = str(result.get("v4_verdict") or "")
    module = result.get("v4_module")
    breakdown = result.get("v4_breakdown") or {}
    module_bd = breakdown.get("module") or {}
    verification_assessment = (breakdown.get("assessment_readiness") or {}).get("verification")
    supp = cfg["suppression"]
    blocking_reason = (breakdown.get("safety_gate") or {}).get("blocking_reason")

    # Public-contract aliases / provenance (always emitted)
    result["raw_score_v4_100"] = raw
    result["quality_score_version"] = cfg["_metadata"]["version"]
    # Clean-label additive flags (titanium dioxide / E171). Emit the consumer
    # "inform" flag for every status, including BLOCKED/UNSAFE suppressed rows;
    # the numeric penalty only applies on the scored path below.
    clean_label_hits = (breakdown.get("safety_gate") or {}).get("clean_label_hits") or []
    cl_penalty, cl_enriched = _clean_label_penalty(clean_label_hits, cfg)
    result["clean_label_flags_v4"] = _build_clean_label_flags(cl_enriched) or None

    # Hard safety failure FIRST (BLOCKED/UNSAFE have raw=None but are NOT "not_scored").
    # Suppress the public number; keep pillars if a breakdown exists (audit trail).
    if verdict in supp["suppressed_safety_verdicts"]:
        result["quality_score_v4_100"] = None
        result["quality_pillars_v4"] = _build_pillars(module_bd, cfg, module, verification_assessment=verification_assessment) if module_bd.get("dimensions") else None
        result["quality_tier"] = None
        result["quality_score_status"] = "suppressed_safety"
        result["quality_score_suppressed_reason"] = blocking_reason or verdict
        return result

    # NOT_SCORED / no usable score
    if raw is None or verdict in supp["not_scored_verdicts"]:
        result["quality_score_v4_100"] = None
        result["quality_pillars_v4"] = None
        result["quality_tier"] = None
        result["quality_score_status"] = "not_scored"
        result["quality_score_suppressed_reason"] = blocking_reason or (verdict or None)
        return result

    pillars = _build_pillars(module_bd, cfg, module, clean_label_penalty=cl_penalty,
                             catalog_caution=verdict == "CAUTION",
                             verification_assessment=verification_assessment)
    # The public total is the literal sum of the six published pillars. No
    # post-sum cap, clamp or category adjustment may change it; a category
    # concern belongs in its owning pillar or the safety gate.
    total = max(0.0, min(100.0, round(sum(p["score"] for p in pillars.values()), 1)))

    # Attach optional, versioned explanation facts sourced from the module
    # breakdown metadata. Pure adapter over already-computed pillars: it never
    # changes score/max/reason or the total above.
    pillars = attach_pillar_explanations(pillars, module_bd, cfg, module)
    pillars = _attach_score_receipts(pillars, module_bd, cfg, _archetype(module, module_bd))

    # Scored (SAFE / CAUTION — CAUTION keeps the score, verdict stays prominent elsewhere)
    result["quality_score_v4_100"] = total
    result["quality_pillars_v4"] = pillars
    # Tier from the shipped whole number, so the band name can never disagree
    # with the score printed beside it.
    result["quality_tier"] = _tier(shipped_whole_score(total))
    # Quality tiers never rewrite the independent safety/readiness disposition.
    result["quality_score_status"] = "scored"
    result["quality_score_suppressed_reason"] = None
    return result
