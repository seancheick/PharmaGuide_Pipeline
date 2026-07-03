"""v4 Layer 2 — Completeness Gate.

Decides whether an enriched product has enough structured identity to enter
the live catalog and score pipeline. This is deliberately narrower than
quality scoring: only missing usable identity/payload yields NOT_SCORED.
Missing disclosure such as dose, CFU, EPA/DHA breakdown, form factor, or
mapped coverage is surfaced as soft debt for module scoring, confidence, and
user-facing explanation.

Per SCORING_V4_PROPOSAL.md §4 Layer 2:

  completeness fail → is_live_eligible=false
                    → verdict=NOT_SCORED (archive / QA only)
                    → excluded from the live Flutter catalog

The gate is class-aware. A probiotic with named strains but no CFU, an omega
with fish-oil identity but no EPA/DHA breakdown, or a sports product with a
primary active but missing dose remains scoreable. Those gaps are not hidden:
they are carried as `soft_missing` tags, never as score caps or verdict
ceilings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from scoring_input_contract import classify_ingredient_roles, get_scoring_ingredients

MAPPED_COVERAGE_MIN = 0.85
MULTI_DOSE_COVERAGE_MIN = 0.60
SPORTS_PRIMARY_IDENTITY_CANONICALS = {
    "protein",
    "whey_protein",
    "casein",
    "pea_protein",
    "rice_protein",
    "soy_protein",
    "creatine_monohydrate",
    "beta-alanine",
    "beta_alanine",
    "l_citrulline",
    "hmb",
    "l_leucine",
    "l_isoleucine",
    "l_valine",
}


@dataclass
class CompletenessResult:
    """Outcome of the Layer 2 completeness gate."""

    module: str = "generic"
    is_live_eligible: bool = False
    verdict: Optional[str] = "NOT_SCORED"
    reason: Optional[str] = "incomplete_product_data"
    missing_fields: List[str] = field(default_factory=list)
    mapped_coverage: float = 0.0
    dose_coverage: Optional[float] = None
    checked_fields: List[str] = field(default_factory=list)
    soft_missing: List[str] = field(default_factory=list)
    score_cap: Optional[float] = None
    verdict_ceiling: Optional[str] = None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _as_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(get_scoring_ingredients(product or {}, strict=True).rows)


def _has_active_identity(ingredient: Dict[str, Any]) -> bool:
    return bool(
        ingredient.get("canonical_id")
        or ingredient.get("matched_id")
        or ingredient.get("ingredient_id")
        or ingredient.get("mapped") is True
    )


def _dose_value(ingredient: Dict[str, Any]) -> Optional[float]:
    for key in ("dose", "amount", "quantity", "dosage", "daily_value_amount"):
        value = _as_float(ingredient.get(key), None)
        if value is not None and value > 0:
            return value
    return None


def _dose_unit(ingredient: Dict[str, Any]) -> str:
    for key in (
        "unit",
        "unit_normalized",
        "normalized_unit",
        "dose_unit",
        "amount_unit",
        "dosage_unit",
        "quantity_unit",
    ):
        unit = _norm(ingredient.get(key))
        if unit and unit not in {"np", "n/a", "na", "none"}:
            return unit
    return ""


def _has_dose_with_unit(ingredient: Dict[str, Any]) -> bool:
    return _dose_value(ingredient) is not None and bool(_dose_unit(ingredient))


def _daily_value_percent(ingredient: Dict[str, Any]) -> Optional[float]:
    for key in ("daily_value", "dailyValue"):
        value = _as_float(ingredient.get(key), None)
        if value is not None and value > 0:
            return value
    raw_taxonomy = _safe_dict(ingredient.get("raw_taxonomy"))
    for variant in _safe_list(raw_taxonomy.get("quantityVariants")):
        if not isinstance(variant, dict):
            continue
        value = _as_float(variant.get("daily_value"), None)
        if value is not None and value > 0:
            return value
        for target in _safe_list(variant.get("dailyValueTargetGroup")):
            if not isinstance(target, dict):
                continue
            value = _as_float(target.get("percent"), None)
            if value is not None and value > 0:
                return value
    return None


def _has_percent_dv_only_evidence(ingredient: Dict[str, Any]) -> bool:
    unit = _dose_unit(ingredient)
    return not unit and _dose_value(ingredient) is not None and _daily_value_percent(ingredient) is not None


# Enzyme activity units — digestive enzymes are dosed by activity, not mass.
# The enricher marks these rows dose_class='enzyme_activity' (mass quantity
# stays 0/NP because the meaningful dose is the activity unit).
_ENZYME_ACTIVITY_UNITS = {
    "alu", "ppi", "blgu", "hut", "sapu", "fip", "cu", "gdu", "dppiv", "dpp-iv",
    "lacu", "fccpu", "au", "skb", "mwu", "pu", "dp", "ckpu", "aju", "usp",
}


def _has_enzyme_activity_evidence(ingredient: Dict[str, Any]) -> bool:
    """True when an ingredient carries enzyme-activity dose evidence.

    Enzymes are dosed in activity units (ALU/PPI/BLGU/...), so their mass
    quantity is legitimately 0/NP. The enricher classifies these rows as
    dose_class='enzyme_activity' with an activity_unit. v4 must treat that as
    valid dose evidence rather than blocking the product as 'missing dose'.
    """
    if _norm(ingredient.get("dose_class")) != "enzyme_activity":
        return False
    return bool(
        _norm(ingredient.get("activity_unit"))
        or _as_float(ingredient.get("activity_value"), None)
        or _norm(ingredient.get("unit")) in _ENZYME_ACTIVITY_UNITS
    )


def _has_usable_dose_evidence(ingredient: Dict[str, Any]) -> bool:
    """Dose evidence for live-eligibility: a mass dose+unit OR enzyme activity."""
    return (
        _has_dose_with_unit(ingredient)
        or _has_enzyme_activity_evidence(ingredient)
        or _has_percent_dv_only_evidence(ingredient)
    )


def _mapped_coverage(product: Dict[str, Any], ingredients: List[Dict[str, Any]]) -> float:
    scoring_input = get_scoring_ingredients(product or {}, strict=True)
    if scoring_input.mapped_coverage is not None:
        return round(scoring_input.mapped_coverage, 4)
    return 0.0


def _form_factor(product: Dict[str, Any]) -> str:
    """Return a usable form-factor string. SP-3 (2026-05-21): prefer
    `form_factor_canonical` (the SP-3 normalizer output) over legacy
    free-text fields. `unknown` and empty string are both treated as
    missing so the completeness gate still flags "no form factor data".
    """
    canonical = _norm(product.get("form_factor_canonical"))
    if canonical and canonical != "unknown":
        return canonical
    for key in ("form_factor", "product_form", "dosage_form", "form"):
        value = _norm(product.get(key))
        if value:
            return value
    return ""


def _status_is_active(product: Dict[str, Any]) -> bool:
    status = _norm(product.get("product_status") or product.get("status"))
    if not status:
        # Legacy enriched blobs may omit status. P1.2 treats missing as
        # unknown-but-eligible; the active-only catalog gate is P0.3.
        return True
    return status in {"active", "on_market", "on market", "marketed", "current"}


def _base_checks(product: Dict[str, Any], ingredients: List[Dict[str, Any]]) -> tuple[List[str], float]:
    missing: List[str] = []
    coverage = _mapped_coverage(product, ingredients)
    if not ingredients or not any(_has_active_identity(i) for i in ingredients):
        missing.append("active_identity")
    return missing, coverage


def _total_cfu_billion(product: Dict[str, Any]) -> float:
    pdata = _safe_dict(product.get("probiotic_data"))
    total = _as_float(pdata.get("total_billion_count"), None)
    if total is not None and total > 0:
        return total
    total = 0.0
    for blend in _safe_list(pdata.get("probiotic_blends")):
        if not isinstance(blend, dict):
            continue
        cfu_data = _safe_dict(blend.get("cfu_data"))
        total += _as_float(cfu_data.get("billion_count"), 0.0) or 0.0
    return total or 0.0


def _named_strain_count(product: Dict[str, Any]) -> int:
    pdata = _safe_dict(product.get("probiotic_data"))
    explicit = int(_as_float(pdata.get("total_strain_count"), 0) or 0)
    if explicit > 0:
        return explicit

    strains = set()
    for blend in _safe_list(pdata.get("probiotic_blends")):
        if not isinstance(blend, dict):
            continue
        for strain in _safe_list(blend.get("strains")):
            name = str(strain).strip()
            if name:
                strains.add(name.lower())
    return len(strains)


def _dose_coverage(ingredients: List[Dict[str, Any]]) -> float:
    if not ingredients:
        return 0.0
    dose_count = sum(1 for i in ingredients if _has_dose_with_unit(i))
    return round(dose_count / len(ingredients), 4)


def _finalize(
    module: str,
    missing: List[str],
    mapped_coverage: float,
    dose_coverage: Optional[float],
    checked_fields: List[str],
    *,
    soft_missing: Optional[List[str]] = None,
    score_cap: Optional[float] = None,
    verdict_ceiling: Optional[str] = None,
) -> CompletenessResult:
    # Preserve first occurrence order while removing duplicates.
    unique_missing = list(dict.fromkeys(missing))
    unique_soft_missing = list(dict.fromkeys(soft_missing or []))
    eligible = not unique_missing
    return CompletenessResult(
        module=module,
        is_live_eligible=eligible,
        verdict=None if eligible else "NOT_SCORED",
        reason=None if eligible else "incomplete_product_data",
        missing_fields=unique_missing,
        mapped_coverage=round(mapped_coverage, 4),
        dose_coverage=dose_coverage,
        checked_fields=checked_fields,
        soft_missing=unique_soft_missing,
        score_cap=score_cap,
        verdict_ceiling=verdict_ceiling,
    )


def _product_evidence_rows(ingredients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        ing for ing in ingredients
        if ing.get("scoring_input_kind") == "product_level_evidence"
    ]


def _has_product_evidence(ingredients: List[Dict[str, Any]], evidence_type: str) -> bool:
    target = _norm(evidence_type)
    return any(_norm(row.get("evidence_type")) == target for row in _product_evidence_rows(ingredients))


def _has_sports_primary_identity_signal(product: Dict[str, Any]) -> bool:
    scoring_input = get_scoring_ingredients(product or {}, strict=True)
    for rejected in scoring_input.rejected_rows:
        row = rejected.row if isinstance(rejected.row, dict) else {}
        if rejected.reason not in {
            "missing_dose_evidence",
            "product_evidence_not_scoreable:missing_primary_sports_dose",
        }:
            continue
        if _norm(row.get("canonical_id")) in SPORTS_PRIMARY_IDENTITY_CANONICALS:
            return True
    return False


_PROBIOTIC_IDENTITY_TOKENS = (
    "probiotic",
    "lactobacillus",
    "bifidobacterium",
    "bacillus_coagulans",
    "streptococcus_salivarius",
    "saccharomyces_boulardii",
)


def _has_probiotic_relevant_identity(product: Dict[str, Any], ingredients: List[Dict[str, Any]]) -> bool:
    """True when the scoring contract contains usable probiotic identity.

    Taxonomy/name can route a product to the probiotic module, but the clinical
    score still needs probiotic-relevant contract evidence. A recovered
    non-probiotic row such as glucose must not satisfy the active-identity gate
    for probiotic scoring. Named strains in product-level probiotic_data are
    also valid identity evidence; many disclosed probiotic blends list strains
    under the blend and provide aggregate CFU, so no flat scorable row exists.
    """
    if _named_strain_count(product) > 0:
        return True
    if _has_product_evidence(ingredients, "probiotic_cfu"):
        return True
    for ing in ingredients:
        identity = " ".join(
            _norm(ing.get(key))
            for key in ("canonical_id", "name", "standard_name", "standardName")
        )
        if any(token in identity for token in _PROBIOTIC_IDENTITY_TOKENS):
            return True
    return False


def _has_sports_relevant_identity(product: Dict[str, Any], ingredients: List[Dict[str, Any]]) -> bool:
    """True when the scoring contract contains usable sports identity.

    Identity uses the BROAD ``_SPORTS_IDENTITY_CANONICALS`` set (pre-workout /
    recovery actives such as alpha-GPC, ATP, betaine, taurine, caffeine, the BCAA
    aggregate, and arginine/glutamine/carnitine), not the narrower dose-scored
    ``_SPORTS_ACTIVE_CANONICALS``. This lets the sports gate FAIL OPEN (soft debt)
    like the omega gate for bona fide sports products whose primary dose the rubric
    scores conservatively, instead of forcing NOT_SCORED. Only sports-ROUTED
    products reach this check, so the broader set cannot pull non-sports products in.
    """
    if _has_product_evidence(ingredients, "sports_primary_dose"):
        return True
    if _has_sports_primary_identity_signal(product):
        return True
    return any(_norm(ing.get("canonical_id")) in _SPORTS_IDENTITY_CANONICALS for ing in ingredients)


def _soft_policy_from_scoring_evidence(
    ingredients: List[Dict[str, Any]],
    module: str,
    *,
    cap_eligible_canonicals: Optional[Set[str]] = None,
) -> tuple[List[str], Optional[float], Optional[str]]:
    """Return scoring policy debt introduced by conservative evidence rows.

    Product-level evidence makes v4 scoreable when cleaner/enricher retained
    useful label facts outside normal ingredient rows. An identity-bearing
    blend/header total preserves v3's anchor path and remains an audit-visible
    transparency debt, but it is not a safety signal by itself. Blend opacity is
    penalized inside the transparency dimension; this gate should not double
    punish it with an automatic score cap or CAUTION ceiling.

    ``cap_eligible_canonicals`` is accepted for compatibility with older tests
    and callers, but completeness no longer clamps scores or forces verdicts.
    Evidence rows only emit audit/confidence tags; the score dimensions carry
    the actual penalty.
    """
    evidence_rows = _product_evidence_rows(ingredients)
    evidence_types = {_norm(row.get("evidence_type")) for row in evidence_rows}
    soft_missing: List[str] = []
    score_cap: Optional[float] = None
    verdict_ceiling: Optional[str] = None

    has_conservative_blend_anchor = any(
        _norm(row.get("evidence_type")) == "blend_anchor_mass"
        and (
            _norm(row.get("evidence_scope")) == "blend_level"
            or _norm(row.get("reason")) == "identity_bearing_blend_header_mass"
        )
        for row in evidence_rows
    )
    has_active_anchor = any(
        _norm(row.get("evidence_type")) == "blend_anchor_mass"
        and _norm(row.get("reason")) == "identity_bearing_active_anchor_mass"
        for row in evidence_rows
    )
    has_botanical_active_anchor = any(
        _norm(row.get("evidence_type")) == "blend_anchor_mass"
        and _norm(row.get("reason")) == "identity_bearing_active_anchor_mass"
        and _norm(row.get("anchor_risk_class")) == "botanical_or_standardized"
        for row in evidence_rows
    )
    has_normal_scoring_row = any(
        row.get("scoring_input_kind") != "product_level_evidence"
        for row in ingredients
    )

    if has_conservative_blend_anchor:
        soft_missing.append("conservative_blend_anchor_mass")
    elif has_active_anchor:
        soft_missing.append("active_anchor_mass_evidence")
        if has_botanical_active_anchor and not has_normal_scoring_row:
            # Phase 6: the botanical profile now scores these on real
            # identity/marker/dose, so the interim anchor-only CAUTION ceiling is
            # removed. The audit tag is kept; verdict is left to the score.
            soft_missing.append("botanical_anchor_only_evidence")

    # Enzyme activity is a real dose unit and should not be hard-blocked for
    # lacking mass. If it is paired with a blend/header anchor, the blend policy
    # above carries the caution ceiling.
    if "enzyme_activity" in evidence_types and module in {"generic", "fiber_digestive"}:
        soft_missing.append("enzyme_activity_dose_evidence")

    omega_rows = [
        row for row in _product_evidence_rows(ingredients)
        if _norm(row.get("evidence_type")) == "omega_epa_dha_aggregate"
    ]
    if omega_rows:
        soft_missing.append("omega_aggregate_epa_dha_evidence")
        if any(_norm(row.get("confidence")) == "low" for row in omega_rows):
            soft_missing.append("low_confidence_omega_breakdown")

    if "sports_primary_dose" in evidence_types:
        soft_missing.append("sports_primary_dose_evidence")

    if "probiotic_cfu" in evidence_types:
        soft_missing.append("probiotic_product_cfu_evidence")

    percent_dv_rows = [
        row for row in evidence_rows
        if _norm(row.get("evidence_type")) == "percent_dv_dose"
    ]
    if percent_dv_rows:
        soft_missing.append("percent_dv_only_dose_evidence")

    return soft_missing, score_cap, verdict_ceiling


def evaluate_completeness_gate(product: Dict[str, Any], module: str) -> CompletenessResult:
    """Evaluate the v4 Layer 2 live-catalog eligibility gate.

    Never raises. Missing or malformed product data fails closed to
    NOT_SCORED, except missing legacy `status` which remains eligible
    until the separate active-only catalog gate lands.
    """
    if not isinstance(product, dict):
        return CompletenessResult(
            module=module or "generic",
            missing_fields=["product_payload"],
            checked_fields=["product_payload"],
        )

    module = module if module in {"generic", "probiotic", "multi_or_prenatal", "omega", "sports", "fiber_digestive"} else "generic"
    ingredients = _active_ingredients(product)
    missing, coverage = _base_checks(product, ingredients)
    # Phase 3: role-aware caps. Classify the already-derived rows (no second
    # derivation) and let soft-policy caps fire only for cap-eligible roles.
    roles = classify_ingredient_roles(product, module=module, rows=ingredients)
    cap_eligible_canonicals = {
        cid
        for role in roles
        if role.get("role") in ("primary", "claim_prominent")
        and (cid := _norm(role.get("canonical_id")))
    }
    soft_missing, score_cap, verdict_ceiling = _soft_policy_from_scoring_evidence(
        ingredients,
        module,
        cap_eligible_canonicals=cap_eligible_canonicals,
    )
    checked_fields = [
        "product_status_active",
        "form_factor",
        "active_identity",
        "mapped_coverage",
    ]
    if not _status_is_active(product):
        soft_missing.append("product_status_not_active")
    if not _form_factor(product):
        soft_missing.append("form_factor_not_disclosed")
    if ingredients and coverage < MAPPED_COVERAGE_MIN:
        soft_missing.append("low_mapped_coverage")
    dose_cov: Optional[float] = None

    if module == "probiotic":
        checked_fields.extend(["total_cfu", "named_strain"])
        strain_count = _named_strain_count(product)
        if ingredients and not _has_probiotic_relevant_identity(product, ingredients):
            missing.append("active_identity")
        elif _total_cfu_billion(product) <= 0:
            if strain_count > 0 or ingredients:
                soft_missing.append("total_cfu_not_disclosed")
            else:
                missing.append("total_cfu")
        if strain_count <= 0:
            soft_missing.append("named_strain_not_disclosed")
        # Per-strain CFU and clinical-strain codes are soft fields.
        return _finalize(
            module,
            missing,
            coverage,
            dose_cov,
            checked_fields,
            soft_missing=soft_missing,
            score_cap=score_cap,
            verdict_ceiling=verdict_ceiling,
        )

    if module == "multi_or_prenatal":
        checked_fields.append("micronutrient_panel_dose_coverage")
        dose_cov = _dose_coverage(ingredients)
        # Dose panel coverage is a scoring/confidence signal, not a hard gate.
        # Products with mapped identity still score; the dose dimensions and
        # confidence explain missing disclosure.
        if len(ingredients) >= 8 and dose_cov < MULTI_DOSE_COVERAGE_MIN:
            soft_missing.append("micronutrient_panel_dose_coverage_low")
        elif len(ingredients) < 8 and ingredients and not any(_has_usable_dose_evidence(i) for i in ingredients):
            soft_missing.append("dose_not_disclosed")
        return _finalize(
            module,
            missing,
            coverage,
            dose_cov,
            checked_fields,
            soft_missing=soft_missing,
            score_cap=score_cap,
            verdict_ceiling=verdict_ceiling,
        )

    if module == "omega":
        # Per omega_rubric.completeness_gate: at least one EPA or DHA
        # ingredient with quantity > 0 must be disclosed. Pure-EPA and
        # pure-DHA products (e.g. algal DHA, prescription-grade pure EPA)
        # DO qualify — the gate is 'at least one', not 'both'.
        checked_fields.append("epa_or_dha_disclosed")
        if ingredients and not _has_omega_relevant_identity(ingredients):
            missing.append("active_identity")
        elif not _has_epa_or_dha_disclosed(ingredients) and not _has_product_evidence(
            ingredients,
            "omega_epa_dha_aggregate",
        ):
            soft_missing.append("epa_or_dha_not_disclosed")
        return _finalize(
            module,
            missing,
            coverage,
            dose_cov,
            checked_fields,
            soft_missing=soft_missing,
            score_cap=score_cap,
            verdict_ceiling=verdict_ceiling,
        )

    if module == "sports":
        checked_fields.append("sports_active_dose")
        if ingredients and not _has_sports_relevant_identity(product, ingredients):
            missing.append("active_identity")
        elif not any(_has_sports_active_dose(i) for i in ingredients) and not _has_product_evidence(
            ingredients,
            "blend_anchor_mass",
        ):
            if _has_sports_primary_identity_signal(product):
                soft_missing.append("sports_primary_dose_not_disclosed")
            else:
                soft_missing.append("sports_active_dose_not_disclosed")
        return _finalize(
            module,
            missing,
            coverage,
            dose_cov,
            checked_fields,
            soft_missing=soft_missing,
            score_cap=score_cap,
            verdict_ceiling=verdict_ceiling,
        )

    # Generic module: single nutrients, botanicals, and simple stacks.
    # Omega and sports previously fell through here; both now have branches above.
    # Enzyme-activity rows (dose_class='enzyme_activity', dosed in ALU/PPI/...)
    # count as usable dose evidence even though their mass quantity is 0/NP.
    checked_fields.append("dose_with_unit")
    if not any(_has_usable_dose_evidence(i) for i in ingredients):
        soft_missing.append("dose_not_disclosed")
    return _finalize(
        module,
        missing,
        coverage,
        dose_cov,
        checked_fields,
        soft_missing=soft_missing,
        score_cap=score_cap,
        verdict_ceiling=verdict_ceiling,
    )


_OMEGA_INGREDIENT_CANONICALS = {"epa", "dha", "epa_dha"}
_OMEGA_PARENT_CANONICALS = {
    "fish_oil",
    "krill_oil",
    "cod_liver_oil",
    "algal_oil",
    "algae_oil",
    "omega_3",
    "omega3",
    "omega_3_fatty_acids",
}
_OMEGA_RELEVANT_CANONICALS = _OMEGA_INGREDIENT_CANONICALS | _OMEGA_PARENT_CANONICALS


def _has_omega_relevant_identity(ingredients: List[Dict[str, Any]]) -> bool:
    """True when the scoring contract contains usable omega identity.

    Name/category routing can identify an intended omega product, but the
    clinical score still needs omega-relevant contract evidence. A recovered
    non-omega row such as glucose must not satisfy the active-identity gate for
    an omega module score.
    """
    for ing in ingredients:
        if _norm(ing.get("evidence_type")) == "omega_epa_dha_aggregate":
            return True
        if _norm(ing.get("canonical_id")) in _OMEGA_RELEVANT_CANONICALS:
            return True
    return False


def _has_epa_or_dha_disclosed(ingredients: List[Dict[str, Any]]) -> bool:
    """Return True when at least one EPA or DHA ingredient has a positive
    quantity. Used by the omega completeness gate.

    Field shape from enrich_supplements_v3:
      ingredient_quality_data.ingredients_scorable[].canonical_id ∈ {epa, dha}
      ingredient_quality_data.ingredients_scorable[].quantity > 0
    """
    for ing in ingredients:
        canonical = _norm(ing.get("canonical_id"))
        if canonical not in _OMEGA_INGREDIENT_CANONICALS:
            continue
        if _has_dose_with_unit(ing):
            return True
    return False


_SPORTS_ACTIVE_CANONICALS = {
    "protein",
    "whey_protein",
    "casein",
    "pea_protein",
    "rice_protein",
    "soy_protein",
    "creatine_monohydrate",
    "beta-alanine",
    "beta_alanine",
    "l_citrulline",
    "hmb",
    "l_leucine",
    "l_isoleucine",
    "l_valine",
}

# Broader identity set (vs the dose-scored _SPORTS_ACTIVE_CANONICALS) used ONLY by
# the completeness gate to decide eligibility. These pre-workout / recovery actives
# mark a product as sports nutrition even when the primary-dose rubric scores them
# conservatively, so the sports gate fails open (soft_missing) like the omega gate
# instead of forcing NOT_SCORED. Only sports-ROUTED products reach this check, so the
# broader set cannot pull non-sports products into a sports score. Canonicals here are
# empirically confirmed against the real catalog (alpha_gpc/atp on Thorne Pre-Workout
# Elite 323126; l_arginine/l_glutamine on GNC Amplified Creatine 18538;
# branched_chain_amino_acids on Nutricost BCAA+ 306183/307773; l_carnitine on GNC
# Carnitine 1000 + BCAA 67304) plus standard ISSN pre-workout actives.
_SPORTS_IDENTITY_CANONICALS = _SPORTS_ACTIVE_CANONICALS | {
    # creatine forms (proprietary "creatine matrix" blends often disclose no dose)
    "creatine",
    "creatine_hydrochloride",
    "creatine_hcl",
    "creatine_nitrate",
    "creatine_citrate",
    "buffered_creatine",
    "magnesium_creatine_chelate",
    # amino-acid aggregates / EAA
    "branched_chain_amino_acids",
    "eaa",
    "essential_amino_acids",
    # recovery / nitric-oxide / transport actives
    "l_arginine",
    "l_glutamine",
    "l_carnitine",
    "acetyl_l_carnitine",
    # pre-workout ergogenic actives (dose-scored conservatively in the sports rubric)
    "alpha_gpc",
    "atp",
    "adenosine_triphosphate",
    "betaine",
    "betaine_anhydrous",
    "tmg_betaine",
    "taurine",
    "l_tyrosine",
    "tyrosine",
    "caffeine",
    "caffeine_anhydrous",
    "agmatine",
    "agmatine_sulfate",
}


def _has_sports_active_dose(ingredient: Dict[str, Any]) -> bool:
    return _norm(ingredient.get("canonical_id")) in _SPORTS_ACTIVE_CANONICALS and _has_dose_with_unit(ingredient)
