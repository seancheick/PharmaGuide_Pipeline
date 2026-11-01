"""Generic Dose: approved nutrient contribution and completed-neutral assessments.

Minimum directed daily use determines contribution. Official nutritional
references use the shared PharmaGuide20%-half/100%-full curve; eligible ordinary
adult Mg/Ca purposes use their config-owned contribution targets. A trial amount
is not a minimum-effective benchmark. Unqualified historical anchors never
supply a fallback curve. Maximum-use excess is handled once by the final public
Dose ceiling, independently of these adequacy components.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scoring_v4.modules.botanical_profile import (
    is_botanical_product,
    score_botanical_dose,
    score_botanical_purpose_dose,
)
from scoring_v4.modules.collagen_profile import (
    is_collagen_product,
    score_collagen_dose,
    score_collagen_purpose_dose,
)
from scoring_v4.modules.generic_helpers import (
    get_active_ingredients,
    has_usable_individual_dose,
    missing_doses_are_label_hidden,
    nutrient_delivering_rows,
    delivers_its_nutrient,
    unbenchmarked_dose_credit,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)
from scoring_input_contract import (
    build_scoring_classification,
    ROLE_CLAIM_PROMINENT,
    ROLE_PRIMARY,
    classify_ingredient_roles,
    dose_disclosure_status,
    get_assessable_evidence_ingredients,
    mass_primary_label_actives,
    is_lent_blend_mass,
    source_linked_rows,
    scoring_row_key,
)
from scoring_v4.dose_safety import resolve_dose_safety
from scoring_v4.exposure import quantity_is_unresolved
from dose_assessment import positive_aggregate_clinical_benchmark, positive_clinical_benchmark
from scoring_v4.modules.immune_support import score_immune_purpose_dose, score_immune_support_dose
from scoring_v4.modules.joint_support import score_joint_purpose_dose, score_joint_support_dose
from scoring_v4.modules.sleep_support import score_sleep_purpose_dose, score_sleep_support_dose


# --- Dose 25 weights ------------------------------------------------------

from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "generic")["generic"]


CAP_SUPPLEMENTAL_WINDOW = _DM["cap_supplemental_window"]
DIMENSION_CAP = _DM["dimension_cap"]

# Proxy band cutoffs.
WINDOW_HIGH_SOURCE_PCT = _DM["window_high_source_pct"]    # 21 CFR 101.54(b) "high source"
WINDOW_FULL_ADEQUACY_PCT = _DM["window_full_adequacy_pct"]
# Dose V4.1 §3.1: ordinary-adult contribution-policy targets (elemental mg/day).
_CONTRIBUTION_TARGETS = {key: value for key, value in _DM["contribution_policy_targets"].items()
                         if not key.startswith("_")}
# Life stages that keep their own references instead of the adult targets.
_OWN_REFERENCE_POPULATIONS = frozenset({"pregnancy_lactation", "pediatric"})

PHASE_MARKER = "P1.3.2a_dose_proxy"
METHOD_MARKER = "source_qualified_contribution_and_completed_neutral"

# These nutrients are supplied mainly by food, while ordinary standalone
# supplements intentionally provide only a small fraction of the dietary AI.
# Comparing a normal label dose directly with the full dietary target makes a
# market-standard product look defective. Keep the RDA/AI in nutrient tracking;
# only the generic product-quality proxy excludes it.
_DIETARY_INTAKE_DOMINANT_CANONICALS = frozenset({"potassium", "sodium", "chloride"})

# Which kind of reference an adequacy row's percentage is measured against,
# keyed by the row canonical_id -> rda_optimal_uls.json reference id. Official
# DRI vitamins and trace minerals are judged against the requirement itself.
_DRI_REFERENCE_BY_CANONICAL = {
    "vitamin_a": "vitamin_a", "beta_carotene": "vitamin_a", "alpha_carotene": "vitamin_a",
    "cryptoxanthin": "vitamin_a", "vitamin_c": "vitamin_c", "vitamin_d": "vitamin_d",
    "vitamin_e": "vitamin_e", "vitamin_k": "vitamin_k", "vitamin_k1": "vitamin_k",
    "vitamin_k2": "vitamin_k", "vitamin_b1_thiamine": "thiamin", "vitamin_b2_riboflavin": "riboflavin",
    "vitamin_b3_niacin": "niacin", "vitamin_b5_pantothenic": "pantothenic_acid",
    "vitamin_b6_pyridoxine": "vitamin_b6", "vitamin_b7_biotin": "biotin",
    "vitamin_b9_folate": "folate", "vitamin_b12_cobalamin": "vitamin_b12", "choline": "choline",
    "chromium": "chromium", "copper": "copper", "fluoride": "fluoride", "iodine": "iodine",
    "iron": "iron", "manganese": "manganese", "molybdenum": "molybdenum",
    "selenium": "selenium", "zinc": "zinc",
    "phosphorus": "phosphorus", "alpha_linolenic_acid": "alpha_linolenic_acid",
    "magnesium": "magnesium", "calcium": "calcium",
}

_VITAMIN_DRI_REFERENCES = frozenset(
    reference for canonical, reference in _DRI_REFERENCE_BY_CANONICAL.items()
    if canonical.startswith("vitamin_")
)


def judged_against_vitamin_dri(canonical: object) -> bool:
    """A vitamin or provitamin whose adequacy is read against a vitamin's DRI."""
    reference = _DRI_REFERENCE_BY_CANONICAL.get(_norm_text(canonical))
    return reference is not None and reference in _VITAMIN_DRI_REFERENCES


def _adequacy_reference_kind(canonical: object) -> str:
    key = _norm_text(canonical)
    return "dri" if key in _DRI_REFERENCE_BY_CANONICAL else "no_benchmark"


def nutritional_unit_credit(pct: Optional[float]) -> Optional[float]:
    """The one approved RDA/AI contribution curve, independent of safety.

    Percentages are dietary reference correspondence, not percent effectiveness.
    Panel and nutrient consumers use the same config-owned20/100 thresholds.
    """
    value = _as_float(pct, None)
    if value is None:
        return None
    value = max(0.0, value)
    if value >= WINDOW_FULL_ADEQUACY_PCT:
        return 1.0
    half = 0.5
    if value >= WINDOW_HIGH_SOURCE_PCT:
        return half + half * (value - WINDOW_HIGH_SOURCE_PCT) / (WINDOW_FULL_ADEQUACY_PCT - WINDOW_HIGH_SOURCE_PCT)
    return half * value / WINDOW_HIGH_SOURCE_PCT


# --- Supplemental-window proxy -------------------------------------------


def _band_credit(
    pct_rda: Optional[float],
    pct_ul: Optional[float],
    canonical: object = None,
    row: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """Per-nutrient adequacy credit on the 0-22 scale, at minimum daily use.

    Returns None when the row has no reference percentage (``pct_rda``); the
    caller skips it from the average. ``pct_ul`` is accepted for call-site
    symmetry and deliberately unused: excess is the product-level ceiling's.
    """
    if pct_rda is None:
        return None
    target = _contribution_target(canonical, row)
    if target is not None:
        amount = max(0.0, pct_rda) / 100.0 * float(row["rda_ai"])
        return CAP_SUPPLEMENTAL_WINDOW * min(amount / float(target["target_mg"]), 1.0)
    # Life-stage contexts retain their sourced RDA/AI and use the approved
    # shared nutritional curve. They cannot borrow the ordinary-adult target
    # or the retired quarter-RDA shortcut. Missing source references stay absent.
    if (_norm_text(canonical) in _CONTRIBUTION_TARGETS
            and (not isinstance(row, dict) or (_as_float(row.get("rda_ai"), 0) or 0) <= 0)):
        return None
    if _adequacy_reference_kind(canonical) == "dri":
        credit = nutritional_unit_credit(pct_rda)
        return None if credit is None else CAP_SUPPLEMENTAL_WINDOW * credit
    return None


def _contribution_target(canonical: object, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The ordinary-adult contribution target for this assessment row, if any.

    Only a row the caller vouches for (single-nutrient or declared purpose)
    with a sourced RDA/AI and an ordinary adult population qualifies.
    """
    target = _CONTRIBUTION_TARGETS.get(_norm_text(canonical))
    if target is None or not isinstance(row, dict):
        return None
    rda = _as_float(row.get("rda_ai"), None)
    population = _safe_dict(row.get("ul_population"))
    members = population.get("members") or [population.get("id")]
    if rda is None or rda <= 0 or _OWN_REFERENCE_POPULATIONS.intersection(members):
        return None
    return target


_RECEIPT_EXPOSURE_FIELDS = {"per_day_min": "amount_at_minimum", "per_day_max": "amount_at_maximum",
                             "amount": "amount_per_serving", "unit": "amount_unit"}


def _row_receipt(row: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Amounts and the reference an adequacy row was credited against."""
    rda = _as_float(row.get("rda_ai"), None)
    pct = _as_float(row.get("pct_rda"), None)
    # rda_ul_data rows are the source-owned exposure records; their amounts
    # and reference unit are projected as recorded (as reference_assessments
    # does), never re-derived.
    detail = {name: row.get(key) for key, name in _RECEIPT_EXPOSURE_FIELDS.items()}
    detail.update(reference_value=rda, pct_of_reference=pct)
    target = _contribution_target(row.get("canonical_id"), row) if kind == "contribution_policy_target" else None
    if target is not None and pct is not None and rda:
        amount = pct / 100.0 * rda
        detail.update(reference_value=float(target["target_mg"]),
                      pct_of_reference=round(amount / float(target["target_mg"]) * 100.0, 2))
    if target is not None and target.get("absorption_context_per_administration_mg") is not None:
        # Plan section 3.1: per-administration absorption is context only.
        detail["absorption_context_per_administration_mg"] = float(target["absorption_context_per_administration_mg"])
    return {key: value for key, value in detail.items() if value is not None}


def _assessment_kind(row: Dict[str, Any]) -> str:
    """Which reference an adequacy row was credited against (receipt label)."""
    if _contribution_target(row.get("canonical_id"), row) is not None:
        return "contribution_policy_target"
    return {"dri": "dri_reference", "clinical_anchor": "clinical_anchor"}.get(
        _adequacy_reference_kind(row.get("canonical_id")), "legacy_reference")


def _score_supplemental_window_proxy(product: Dict[str, Any], entries: Optional[List[Dict[str, Any]]] = None) -> tuple[float, Optional[str]]:
    """Average band credit across nutrients with RDA reference data.

    Returns (credit, reason). When no rows have RDA data, returns
    (0.0, "no_rda_reference_data") so the metadata can carry the
    explanation. The public `score_dose` entry point uses this reason
    to avoid converting non-RDA botanicals into a zero Dose score.
    """
    rda_ul = _safe_dict((product or {}).get("rda_ul_data"))
    adequacy_results = _safe_list(rda_ul.get("adequacy_results"))

    contributions: List[float] = []
    dietary_reference_exclusions = 0
    # The ordinary-adult contribution targets apply to a single-nutrient
    # product here; a multi-nutrient formula needs a declared purpose.
    single_nutrient = sum(1 for row in adequacy_results if isinstance(row, dict)
                          and _as_float(row.get("pct_rda"), None) is not None) == 1
    for row in adequacy_results:
        if not isinstance(row, dict):
            continue
        canonical = _norm_text(row.get("canonical_id"))
        nutrient = _norm_text(row.get("nutrient"))
        if canonical in _DIETARY_INTAKE_DOMINANT_CANONICALS or nutrient in _DIETARY_INTAKE_DOMINANT_CANONICALS:
            dietary_reference_exclusions += 1
            continue
        pct_rda = _as_float(row.get("pct_rda"), None)
        pct_ul = _as_float(row.get("pct_ul"), None)
        credit = _band_credit(pct_rda, pct_ul, row.get("canonical_id"), row if single_nutrient else None)
        if credit is None:
            continue
        contributions.append(credit)
        if entries is not None:
            kind = _assessment_kind(row) if single_nutrient else (
                "dri_reference" if _adequacy_reference_kind(row.get("canonical_id")) == "dri"
                else "clinical_anchor" if _adequacy_reference_kind(row.get("canonical_id")) == "clinical_anchor"
                else "legacy_reference")
            entries.append({"ingredient": row.get("nutrient") or row.get("canonical_id"), "assessment": kind,
                            "credit_raw": round(credit, 4), **_row_receipt(row, kind)})

    if not contributions:
        if dietary_reference_exclusions:
            return 0.0, "dietary_intake_dominant_reference_excluded"
        return 0.0, "no_rda_reference_data"

    avg = sum(contributions) / len(contributions)
    return round(_clamp(0.0, CAP_SUPPLEMENTAL_WINDOW, avg), 4), None


def _row_identity_keys(row: Dict[str, Any]) -> set[str]:
    return {
        _norm_text(row.get(key))
        for key in ("canonical_id", "standard_name", "standardName", "name", "nutrient")
        if _norm_text(row.get(key))
    }


def _score_declared_purpose_window(
    product: Dict[str, Any],
) -> tuple[Optional[float], List[str], int, List[Dict[str, Any]], List[Dict[str, Any]], List[float], List[str], List[Dict[str, Any]]]:
    """Score each explicitly declared purpose once, using one equal vote.

    The shared role owner establishes purpose from the route, product title or
    an ingredient-scoped label function claim.  A disclosed purpose with no
    applicable benchmark receives the existing limited-assessability credit;
    an incidental/supporting row does not enter merely because it is present or
    heavy.  Missing required amounts are handled by assessment readiness before
    this route scorer is published.

    Returns the score, unbenchmarked identities, purpose count, benchmark
    assessments, specialized assessments and unbenchmarked fallback values. ``score`` is
    ``None`` when the label declares no purpose row, preserving the legacy
    compatibility path for products whose source has not yet supplied one.
    """
    rows = [row for row in nutrient_delivering_rows(product) if isinstance(row, dict)]
    # Profile eligibility is owned by the shared classification contract, not
    # inferred again from raw registry/taxonomy fields in the Dose consumer.
    botanical_rows = {
        (item.get("row_ref"), item.get("canonical_id"))
        for item in build_scoring_classification(product).get("ingredients", [])
        if item.get("profile_eligibility", {}).get("botanical", {}).get("eligible") is True
    }
    aggregate = positive_aggregate_clinical_benchmark(product, rows)
    aggregate_members = set(aggregate.member_canonical_ids) if aggregate is not None else set()
    # A declared mixture keeps one purpose vote when its clinical numerical
    # benchmark is retired. Identity/purpose and amount ownership are separate
    # from efficacy eligibility; use the existing role and mixture owners.
    from scoring_v4.modules.sports_helpers import BCAA_CANONICALS, EAA_CANONICALS, group_bcaa, group_eaa
    # Source-owned named blend members retain their identities even when the
    # strict dose-bearing projection excludes their hidden amounts. Supplement
    # group membership only; ordinary purpose rows still use the strict owner.
    amino_sources = {scoring_row_key(row, index): row
                     for index, row in enumerate(get_assessable_evidence_ingredients(product, source_bound=True))
                     if delivers_its_nutrient(row)}
    # The strict projection owns a source occurrence over its legacy mirror.
    amino_sources.update({scoring_row_key(row, index): row for index, row in enumerate(rows)})
    eaa_rows = [row for row in amino_sources.values() if _norm_text(row.get("canonical_id")) in EAA_CANONICALS]
    strict_eaa = group_eaa(rows)
    eaa_identity = {"canonical_id": "essential_amino_acids", "name": "EAA"}
    eaa_role = classify_ingredient_roles(product, module="generic", rows=[eaa_identity])[0]
    eaa_declared = (
        aggregate is None
        and not strict_eaa["aggregate_identity_complete"]
        and eaa_role.get("role") in {ROLE_PRIMARY, ROLE_CLAIM_PROMINENT}
        and EAA_CANONICALS <= {_norm_text(row.get("canonical_id")) for row in eaa_rows}
    )
    bcaa_rows = [row for row in amino_sources.values() if _norm_text(row.get("canonical_id")) in BCAA_CANONICALS]
    bcaa_identity = {"canonical_id": "branched_chain_amino_acids", "name": "BCAA"}
    bcaa_role = classify_ingredient_roles(product, module="generic", rows=[bcaa_identity])[0]
    bcaa_whole_owned = any(
        _norm_text(row.get("canonical_id")) == "branched_chain_amino_acids"
        and not quantity_is_unresolved(row)
        and _product_evidence_dose_credit(row)[0] > 0
        for row in rows
    )
    bcaa_declared = (
        aggregate is None
        and not eaa_declared
        and not bcaa_whole_owned
        and bcaa_role.get("role") in {ROLE_PRIMARY, ROLE_CLAIM_PROMINENT}
        and BCAA_CANONICALS <= {_norm_text(row.get("canonical_id")) for row in bcaa_rows}
        and not strict_eaa["complete"]
    )
    amino_group = (("eaa", eaa_rows, group_eaa) if eaa_declared
                   else ("bcaa", bcaa_rows, group_bcaa) if bcaa_declared else None)
    if amino_group:
        aggregate_members.update(EAA_CANONICALS if eaa_declared else BCAA_CANONICALS)
    roles = classify_ingredient_roles(product, module="generic", rows=rows)
    purpose_rows = [
        row for row, role in zip(rows, roles)
        if role.get("role") in {ROLE_PRIMARY, ROLE_CLAIM_PROMINENT}
        and not row.get("is_parent_total")
        and _norm_text(row.get("canonical_id")) not in aggregate_members
    ]
    if not purpose_rows and aggregate is None and amino_group is None:
        return None, [], 0, [], [], [], [], []

    # A physical purpose may have a compatibility projection of the same
    # source row.  Count it once by canonical identity, falling back to source.
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in purpose_rows:
        identity = _norm_text(row.get("canonical_id"))
        source = str(row.get("raw_source_path") or row.get("source_row_ref") or "").strip()
        key = identity or source or _norm_text(row.get("name"))
        if key:
            grouped.setdefault(key, []).append(row)
    # Two source rows of one identity share its vote. The heaviest speaks for
    # it, as in the profile owners' primary, so a small sibling's completed
    # review cannot stand in for the dominant row's (KSM-66 beside a plain
    # ashwagandha powder).
    purposes: Dict[str, Dict[str, Any]] = {}
    for key, group in grouped.items():
        heaviest = mass_primary_label_actives(product, group) if len(group) > 1 else []
        purposes[key] = heaviest[0] if heaviest else group[0]

    adequacy = [
        row for row in _safe_list(_safe_dict(product.get("rda_ul_data")).get("adequacy_results"))
        if isinstance(row, dict)
    ]
    contributions: List[float] = []
    unbenchmarked: List[str] = []
    hidden: List[str] = []
    # One receipt entry per vote (Dose V4.1 section 4): what was assessed,
    # how, and its raw credit. The explanation renders this; it never recomputes.
    entries: List[Dict[str, Any]] = []
    fallback_values: List[float] = []

    def vote(ingredient: str, assessment: str, credit: float, **detail: Any) -> None:
        contributions.append(credit)
        entries.append({"ingredient": ingredient, "assessment": assessment,
                        "credit_raw": round(float(credit), 4),
                        **{key: value for key, value in detail.items() if value is not None}})
    clinical_assessments: List[Dict[str, Any]] = []
    specialized_assessments: List[Dict[str, Any]] = []
    if amino_group:
        identity, members, measure = amino_group
        measured = measure(members)
        hidden_only = missing_doses_are_label_hidden(members)
        if not any(quantity_is_unresolved(row) for row in members) and (measured["complete"] or hidden_only):
            credit = unbenchmarked_dose_credit()
            vote(identity, "hidden_amount_neutral" if hidden_only else "no_benchmark_neutral", credit)
            fallback_values.append(credit)
            (hidden if hidden_only else unbenchmarked).append(identity)
        else:
            vote(identity, "unresolved_source_quantity", 0.0)
    if aggregate is not None:
        # Dose V4.1 section 2.2: the highest studied dose is no upper limit;
        # above it adequacy plateaus. Excess is the product-level ceiling's.
        if aggregate.benchmark_maximum and aggregate.exposure_value > aggregate.benchmark_maximum:
            aggregate_credit = CAP_SUPPLEMENTAL_WINDOW
            aggregate_band = "above_highest_studied_dose"
        elif aggregate.ratio >= 1.0:
            aggregate_credit = CAP_SUPPLEMENTAL_WINDOW
            aggregate_band = "within_studied_range"
        else:
            aggregate_credit = aggregate.ratio * CAP_SUPPLEMENTAL_WINDOW
            aggregate_band = "below_studied_range"
        vote("aggregate_formula", "aggregate_formula_benchmark", _clamp(0.0, CAP_SUPPLEMENTAL_WINDOW, aggregate_credit),
             band=aggregate_band)
        clinical_assessments.append({
            "assessment_kind": "aggregate_formula",
            "dose_band": aggregate_band,
            **aggregate.to_dict(),
        })
    for key, purpose in sorted(purposes.items()):
        identities = _row_identity_keys(purpose)
        specialized = score_collagen_purpose_dose(product, purpose)
        specialized_owner = "collagen_profile"
        if specialized is None and is_botanical_product(product):
            specialized = score_botanical_purpose_dose(product, purpose)
            specialized_owner = "botanical_profile"
        if specialized is None:
            specialized = score_sleep_purpose_dose(product, purpose)
            specialized_owner = "sleep_support"
        if specialized is None:
            specialized = score_joint_purpose_dose(product, purpose)
            specialized_owner = "joint_support"
        if specialized is None:
            specialized = score_immune_purpose_dose(product, purpose)
            specialized_owner = "immune_support"
        if (specialized is None
                and (purpose.get("raw_source_path") or purpose.get("source"),
                     purpose.get("canonical_id")) in botanical_rows):
            # A classified botanical purpose still needs its preparation review
            # when co-formulated nutrients select a non-botanical product route.
            # Preserve the existing specialized owners' precedence.
            specialized = score_botanical_purpose_dose(product, purpose)
            specialized_owner = "botanical_profile"
        if specialized is not None:
            completed_botanical_neutral = (
                specialized_owner == "botanical_profile"
                and specialized.get("band") == "disclosed_no_reference"
                and specialized.get("metadata", {}).get("benchmark") == "absent"
            )
            vote(key, "no_benchmark_neutral" if completed_botanical_neutral else specialized_owner,
                 float(specialized["score"]), band=specialized.get("band"))
            if completed_botanical_neutral:
                fallback_values.append(float(specialized["score"]))
                unbenchmarked.append(key)
            specialized_assessments.append({
                "assessment_owner": specialized_owner,
                **specialized,
            })
            continue
        credits = []
        assessed = []
        for assessment in adequacy:
            if not (identities & _row_identity_keys(assessment)):
                continue
            if _row_identity_keys(assessment) & _DIETARY_INTAKE_DOMINANT_CANONICALS:
                # Same exclusion as the proxy path: an ordinary amount is a
                # small fraction of the dietary AI by design. It is assessed
                # below as a completed neutral, not against the AI.
                continue
            credit = _band_credit(
                _as_float(assessment.get("pct_rda"), None),
                _as_float(assessment.get("pct_ul"), None),
                assessment.get("canonical_id"),
                assessment,
            )
            if credit is not None:
                credits.append(credit)
                assessed.append(assessment)
        if credits:
            # The producer normally emits one canonical assessment.  If a
            # compatibility artifact has duplicates, one purpose still gets
            # one conservative vote rather than extra denominator weight.
            chosen = assessed[credits.index(min(credits))]
            kind = _assessment_kind(chosen)
            vote(key, kind, min(credits), **_row_receipt(chosen, kind))
            continue
        clinical = positive_clinical_benchmark(product, purpose)
        if clinical is not None:
            vote(key, "clinical_benchmark", min(CAP_SUPPLEMENTAL_WINDOW, clinical.ratio * CAP_SUPPLEMENTAL_WINDOW),
                 pct_of_reference=round(clinical.ratio * 100.0, 2))
            clinical_assessments.append(clinical.to_dict())
            continue
        if has_usable_individual_dose(purpose):
            vote(key, "no_benchmark_neutral", unbenchmarked_dose_credit())
            fallback_values.append(unbenchmarked_dose_credit())
            unbenchmarked.append(key)
            continue
        if not is_lent_blend_mass(purpose):
            # A disclosed whole preparation remains assessable at the existing
            # product-evidence fallback. A borrowed child amount cannot own
            # that preparation's contribution in the purpose average.
            credit, _ = _product_evidence_dose_credit(purpose)
            if credit:
                vote(key, "no_benchmark_neutral", credit)
                fallback_values.append(credit)
                unbenchmarked.append(key)
                continue
        if not quantity_is_unresolved(purpose) and (
                is_lent_blend_mass(purpose) or dose_disclosure_status(purpose) == "not_disclosed_blend"):
            # Dose V4.1 section 2.3: a declared purpose whose amount the label
            # hides (a blend member printed without its own amount) keeps its
            # one vote at the shared neutral; Transparency keeps the
            # disclosure consequence. A pipeline-lost amount (unresolved
            # quantity) keeps its strict readiness hold, and a row missing an
            # amount without a label nondisclosure earns no vote.
            vote(key, "hidden_amount_neutral", unbenchmarked_dose_credit())
            fallback_values.append(unbenchmarked_dose_credit())
            hidden.append(key)

    if not contributions:
        return 0.0, sorted(unbenchmarked), len(purposes) + int(aggregate is not None) + int(amino_group is not None), clinical_assessments, specialized_assessments, fallback_values, sorted(hidden), entries
    return (
        round(_clamp(0.0, CAP_SUPPLEMENTAL_WINDOW, sum(contributions) / len(contributions)), 4),
        sorted(unbenchmarked),
        len(purposes) + int(aggregate is not None) + int(amino_group is not None),
        clinical_assessments,
        specialized_assessments,
        fallback_values,
        sorted(hidden),
        entries,
    )


def _score_no_reference_quantified_dose(product: Dict[str, Any]) -> tuple[float, Optional[str]]:
    """Conservative partial dose credit when no RDA/UL table exists.

    Botanicals, amino acids, enzymes, and specialty actives often have real
    label doses but no RDA/UL benchmark. That evidence is clinically usable:
    it should not receive full "inside supplemental window" credit, but it
    also should not make the dose dimension disappear. Cleaner/enricher-owned
    product_scoring_evidence is used for aggregate/blend/activity evidence.
    """
    for ingredient in nutrient_delivering_rows(product):
        if not isinstance(ingredient, dict):
            continue
        if ingredient.get("is_parent_total"):
            continue
        dose_class = _norm_text(ingredient.get("dose_class"))
        quantity = _as_float(ingredient.get("quantity"), None)
        if dose_class == "enzyme_activity" and quantity is not None and quantity > 0:
            return unbenchmarked_dose_credit(), "enzyme_activity_quantified_dose_no_rda_reference"
        if dose_class == "probiotic_cfu" and quantity is not None and quantity > 0:
            return unbenchmarked_dose_credit(), "probiotic_cfu_quantified_dose_no_rda_reference"
        if has_usable_individual_dose(ingredient):
            return unbenchmarked_dose_credit(), "individual_quantified_dose_no_rda_reference"

    for evidence in _safe_list(product.get("product_scoring_evidence")):
        credit, reason = _product_evidence_dose_credit(evidence)
        if credit:
            return credit, reason

    return 0.0, None


def _product_evidence_dose_credit(evidence: Any) -> tuple[float, Optional[str]]:
    """Existing limited-assessment credit for a disclosed preparation."""
    if not isinstance(evidence, dict) or not evidence.get("scoreable"):
        return 0.0, None
    dose_value = _as_float(evidence.get("dose_value"), None)
    if dose_value is None or dose_value <= 0:
        return 0.0, None
    dose_class = _norm_text(evidence.get("dose_class"))
    if dose_class not in {"therapeutic_mass", "enzyme_activity", "probiotic_cfu"}:
        return 0.0, None
    if _norm_text(evidence.get("evidence_type")) == "blend_anchor_mass":
        return unbenchmarked_dose_credit(), "blend_anchor_quantified_dose_no_rda_reference"
    return unbenchmarked_dose_credit(), "product_evidence_quantified_dose_no_rda_reference"


def _mass_primary_without_reference(product: Dict[str, Any]) -> Optional[str]:
    """Identity of a mass-primary label active that has no usable assessment.

    The scoring contract decides which rows are the primaries (shared source
    ownership, no opaque totals, no unmapped identities, every row tied at the
    top mass). An adequacy row counts as an assessment only when the window
    proxy could band it (`_band_credit` is not None): a row with no reference
    percentage assesses nothing. When several primaries lack an assessment the
    first by identity is named, so the decision is the same for any label
    order.
    """
    assessed: set[str] = set()
    for row in _safe_list(_safe_dict((product or {}).get("rda_ul_data")).get("adequacy_results")):
        if not isinstance(row, dict):
            continue
        if _band_credit(_as_float(row.get("pct_rda"), None), _as_float(row.get("pct_ul"), None), row.get("canonical_id"), row) is None:
            continue
        assessed.update(
            _norm_text(row.get(key)) for key in ("canonical_id", "nutrient") if row.get(key)
        )
    active_rows = nutrient_delivering_rows(product)
    for primary in mass_primary_label_actives(product, active_rows):
        # An assessment is source-linked: it may sit on the primary itself, on
        # a projection of the same label row, or on a constituent the row
        # declares (ALA under flaxseed oil). The contract owns that lineage.
        identities = {
            _norm_text(linked_row.get(key))
            for linked_row in (primary, *source_linked_rows(product, primary, active_rows))
            for key in ("canonical_id", "standard_name", "name", "nutrient")
            if linked_row.get(key)
        }
        if identities and not (identities & assessed):
            return _norm_text(primary.get("canonical_id") or primary.get("standard_name") or primary.get("name"))
    return None


# --- B7 dose safety penalty ----------------------------------------------


def _select_window_component(
    *,
    window_credit: float,
    no_reference_credit: float,
    no_rda_reference: bool,
) -> float:
    """Choose the dose-window signal that actually applies.

    The fallback credit answers "a dose is disclosed but no reference range
    exists". It applies when there is no reference — never merely because the
    evaluated window came out at zero. An evaluated 0.0 means the evaluated amounts contributed no adequacy; that is
    a finding, not a missing value.
    """
    return no_reference_credit if no_rda_reference else window_credit


# --- Public entry point --------------------------------------------------


def _unread_declared_purpose_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Source-role purposes whose captured amount cannot be assessed.

    Shared by ordinary-purpose and aggregate-route consumers. Label-hidden
    blend children stay distinct from missing pipeline amounts.
    """
    source_rows = [row for row in nutrient_delivering_rows(product) if isinstance(row, dict)]
    source_roles = classify_ingredient_roles(product, module="generic", rows=source_rows)
    unread = [row for row, role in zip(source_rows, source_roles)
              if role.get("role") in {ROLE_PRIMARY, ROLE_CLAIM_PROMINENT}
              and not row.get("is_parent_total")
              and dose_disclosure_status(row) != "not_disclosed_blend"
              and not is_lent_blend_mass(row)
              and (quantity_is_unresolved(row) or (
                  not has_usable_individual_dose(row, allow_zero=True)
                  and _product_evidence_dose_credit(row)[0] <= 0))]
    # A completed botanical no-benchmark assessment needs disclosure, not a
    # mass conversion. Keep unresolved source quantities blocked even when
    # their captured numeric value looks usable.
    if is_botanical_product(product):
        unread = [row for row in unread if quantity_is_unresolved(row) or not (
            (assessment := score_botanical_purpose_dose(product, row))
            and assessment.get("band") == "disclosed_no_reference"
            and assessment.get("metadata", {}).get("benchmark") == "absent"
        )]
    return unread


def score_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute source-qualified contribution or completed-neutral Dose credit.

    Args:
        product: Enriched product dict. Treated as empty if not a dict.

    Returns:
        Dict with shape:
            {
                "score": <float, clamped to [0, 25]> | None,
                "max": 25.0,
                "components": {
                    "supplemental_window_proxy": <0..22>,
                },
                "penalties": {},
                "phase": "P1.3.2a_dose_proxy",
                "metadata": {
                    "phase": "P1.3.2a_dose_proxy",
                    "method": "source_qualified_contribution_and_completed_neutral",
                    "window_proxy_reason": "no_rda_reference_data" | absent,
                    "window_proxy_status": "not_evaluable_by_rda_proxy" | absent,
                },
            }

    The historical phase identifier remains compatible. Method and reference
    assessments identify the approved policy and completed scientific review.
    """
    if not isinstance(product, dict):
        product = {}
    b7_metadata = resolve_dose_safety(product).audit_metadata()
    (
        purpose_credit,
        unbenchmarked_purposes,
        purpose_count,
        clinical_benchmarks,
        specialized_purpose_assessments,
        purpose_fallback_values,
        hidden_purposes,
        purpose_entries,
    ) = (
        _score_declared_purpose_window(product)
    )

    unread = _unread_declared_purpose_rows(product)
    if unread or any(item.get("assessment") == "unresolved_source_quantity" for item in purpose_entries):
        return {"score": None, "max": DIMENSION_CAP,
                "components": {"supplemental_window_proxy": 0.0}, "penalties": {},
                "phase": PHASE_MARKER,
                "metadata": {"phase": PHASE_MARKER, "method": METHOD_MARKER,
                             "assessment_status": "incomplete",
                             "reason_code": "unresolved_source_quantity",
                             "B7_safety_evaluation": b7_metadata}}

    # Phase 7 — Collagen Profile: per-subtype clinical dose range (unit-aware) so an
    # underdosed collagen no longer borrows its co-formulated vitamins' RDA dose.
    # Checked before botanical (mass-dominance makes them mutually exclusive).
    if purpose_count <= 1 and is_collagen_product(product):
        col = score_collagen_dose(product)
        components = {
            "collagen_clinical_dose": round(float(col["score"]), 4),
        }
        penalties: Dict[str, float] = {}
        score = _clamp(0.0, DIMENSION_CAP, float(col["score"]))
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "collagen_clinical_dose_v1",
                "dose_participation_basis": "single_profile_assessment",
                "dose_contributions": [{"ingredient": "collagen", "assessment": "collagen_profile",
                                        "band": col.get("band"), "credit_raw": round(float(col["score"]), 4)}],
                "collagen_dose_band": col["band"],
                "collagen_dose": col.get("metadata", {}),
                "B7_safety_evaluation": b7_metadata,
            },
        }

    # Phase 6 — Botanical Profile: clinical therapeutic-range dose (via
    # rda_therapeutic_dosing.json) instead of the RDA/UL proxy. Always evaluable
    # (never None), so the dose dimension is no longer excluded for botanicals
    # and the Phase-4 botanical_dose_deferred floor guard is superseded.
    if purpose_count <= 1 and is_botanical_product(product):
        purpose_botanical = next((
            assessment for assessment in specialized_purpose_assessments
            if assessment.get("assessment_owner") == "botanical_profile"
        ), None)
        bot = purpose_botanical or score_botanical_dose(product)
        components = {
            "botanical_clinical_dose": round(float(bot["score"]), 4),
        }
        penalties: Dict[str, float] = {}
        score = _clamp(0.0, DIMENSION_CAP, float(bot["score"]))
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "botanical_clinical_dose_v1",
                "dose_participation_basis": "single_profile_assessment",
                "dose_contributions": [{"ingredient": "botanical", "assessment": (
                    "no_benchmark_neutral" if bot.get("band") == "disclosed_no_reference"
                    and bot.get("metadata", {}).get("benchmark") == "absent" else "botanical_profile"),
                                        "band": bot.get("band"), "credit_raw": round(float(bot["score"]), 4)}],
                "botanical_dose_band": bot["band"],
                "botanical_dose": bot.get("metadata", {}),
                "B7_safety_evaluation": b7_metadata,
            },
        }

    sleep = score_sleep_support_dose(product) if purpose_count <= 1 else None
    if sleep is not None:
        components = {
            "sleep_support_dose": round(float(sleep["score"]), 4),
        }
        penalties: Dict[str, float] = {}
        score = _clamp(0.0, DIMENSION_CAP, float(sleep["score"]))
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "sleep_support_clinical_dose_v1",
                "dose_participation_basis": "single_profile_assessment",
                "dose_contributions": [{"ingredient": "sleep support", "assessment": "sleep_support",
                                        "band": sleep.get("band"), "credit_raw": round(float(sleep["score"]), 4)}],
                "sleep_support_dose": sleep,
                "B7_safety_evaluation": b7_metadata,
            },
        }

    immune = score_immune_support_dose(product) if purpose_count == 0 else None
    if immune is not None:
        components = dict(immune["components"])
        penalties: Dict[str, float] = {}
        score = _clamp(0.0, DIMENSION_CAP, float(immune["score"]))
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "immune_support_daily_dose_v1",
                "dose_participation_basis": "single_profile_assessment",
                "dose_contributions": [{"ingredient": "immune support", "assessment": "immune_support",
                                        "band": immune.get("band"), "credit_raw": round(float(immune["score"]), 4)}],
                "immune_support_dose": immune.get("metadata", {}),
                "B7_safety_evaluation": b7_metadata,
            },
        }

    joint = score_joint_support_dose(product) if purpose_count <= 1 else None
    if joint is not None:
        components = {
            "joint_support_dose": round(float(joint["score"]), 4),
        }
        penalties: Dict[str, float] = {}
        score = _clamp(0.0, DIMENSION_CAP, float(joint["score"]))
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "joint_support_clinical_dose_v1",
                "dose_participation_basis": "single_profile_assessment",
                "dose_contributions": [{"ingredient": "joint support", "assessment": "joint_support",
                                        "band": joint.get("band"), "credit_raw": round(float(joint["score"]), 4)}],
                "joint_support_dose": joint,
                "B7_safety_evaluation": b7_metadata,
            },
        }

    proxy_entries: List[Dict[str, Any]] = []
    window_credit, window_reason = _score_supplemental_window_proxy(product, proxy_entries)
    if purpose_credit is not None:
        window_credit = purpose_credit
        window_reason = None
    no_rda_reference = window_reason in {
        "no_rda_reference_data",
        "dietary_intake_dominant_reference_excluded",
    }
    no_reference_credit = 0.0
    no_reference_credit_reason: Optional[str] = None
    if no_rda_reference:
        no_reference_credit, no_reference_credit_reason = _score_no_reference_quantified_dose(product)
    unassessed_primary: Optional[str] = None
    if not no_rda_reference and purpose_credit is None:
        unassessed_primary = _mass_primary_without_reference(product)
        if unassessed_primary and window_credit > unbenchmarked_dose_credit():
            # The assessed nutrients' window average must not present a
            # complete product-dose assessment while the mass-primary active
            # has no reference at all; it can earn no more than the existing
            # partial credit for a disclosed dose without a reference.
            window_credit = unbenchmarked_dose_credit()

    components: Dict[str, float] = {
        "supplemental_window_proxy": round(
            _select_window_component(
                window_credit=window_credit,
                no_reference_credit=no_reference_credit,
                no_rda_reference=no_rda_reference,
            ),
            4,
        ),
    }
    penalties: Dict[str, float] = {}

    positive = components["supplemental_window_proxy"]
    penalty_total = _sum_penalty_magnitudes(penalties)
    no_rda_reference = window_reason in {
        "no_rda_reference_data",
        "dietary_intake_dominant_reference_excluded",
    }
    if no_rda_reference and no_reference_credit <= 0:
        # Botanicals / herbal actives can have clinically meaningful mg
        # dosing with no RDA/UL reference. Fail open as "not evaluable by
        # this proxy" rather than treating missing dietary-reference data
        # as a poor dose.
        score: Optional[float] = None
    else:
        score = _clamp(0.0, DIMENSION_CAP, positive - penalty_total)

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "method": METHOD_MARKER,
        "B7_safety_evaluation": b7_metadata,
        # Source-owned context, not another assessment or a clinical efficacy claim.
        "reference_assessments": [
            {key: row.get(key) for key in (
                "nutrient", "canonical_id", "unit", "rda_ai", "rda_ai_source", "ul", "ul_status",
                "pct_rda", "pct_ul", "per_day_min", "per_day_max", "reference_profile", "reference",
                "scoring_eligible", "skip_ul_check", "ul_gate_eligible", "source_label_key",
            )}
            for row in _safe_list(_safe_dict(product.get("rda_ul_data")).get("adequacy_results"))
            if isinstance(row, dict)
        ],
        "supplemental_window_max_raw": CAP_SUPPLEMENTAL_WINDOW,
    }
    if purpose_credit is None and proxy_entries and not no_rda_reference:
        metadata["dose_participation_basis"] = "assessed_nutrient_average"
        metadata["dose_contributions"] = proxy_entries
    if purpose_credit is not None:
        metadata["dose_participation_basis"] = "declared_purpose_equal_weight"
        metadata["purpose_ingredient_count"] = purpose_count
        metadata["unbenchmarked_purpose_ingredients"] = unbenchmarked_purposes
        metadata["positive_clinical_benchmark_assessments"] = clinical_benchmarks
        metadata["specialized_purpose_assessments"] = specialized_purpose_assessments
        metadata["dose_contributions"] = purpose_entries
        if hidden_purposes:
            metadata["hidden_amount_purpose_ingredients"] = hidden_purposes
        aggregate_assessment = next((
            assessment for assessment in clinical_benchmarks
            if assessment.get("assessment_kind") == "aggregate_formula"
        ), None)
        if aggregate_assessment is not None:
            metadata["aggregate_dose_band"] = aggregate_assessment["dose_band"]
            metadata["aggregate_clinical_benchmark"] = {
                key: value for key, value in aggregate_assessment.items()
                if key not in {"assessment_kind", "dose_band"}
            }
        if unbenchmarked_purposes:
            metadata["window_proxy_status"] = "limited_assessability_unbenchmarked_purpose"
            # V4.1 Step 4: a whole preparation and an individual amount share
            # the one unbenchmarked neutral, so the fallback has one value.
            metadata["partial_credit_value"] = purpose_fallback_values[0]
    if window_reason is not None:
        metadata["window_proxy_reason"] = window_reason
    if unassessed_primary:
        metadata["primary_active_unassessed"] = unassessed_primary
        if components["supplemental_window_proxy"] <= unbenchmarked_dose_credit():
            metadata["window_proxy_status"] = "partial_credit_primary_active_unassessed"
            metadata["partial_credit_value"] = round(components["supplemental_window_proxy"], 4)
    if no_rda_reference:
        if no_reference_credit > 0:
            metadata["window_proxy_status"] = "partial_credit_without_rda_proxy"
            metadata["partial_credit_reason"] = no_reference_credit_reason
            metadata["partial_credit_value"] = round(no_reference_credit, 4)
        else:
            metadata["window_proxy_status"] = "not_evaluable_by_rda_proxy"

    return {
        "score": round(score, 4) if score is not None else None,
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


# --- internals -----------------------------------------------------------


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))


def _sum_penalty_magnitudes(penalties: Dict[str, float]) -> float:
    return sum(abs(_as_float(v, 0.0) or 0.0) for v in penalties.values())
