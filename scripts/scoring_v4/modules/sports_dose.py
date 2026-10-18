"""v4 sports-module Dose dimension.

Source-qualified sports contributions use approved targets. Reviewed study
regimens without a general benchmark remain descriptive and completed neutral.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from dataclasses import asdict

from scoring_v4.exposure import row_exposure

from scoring_v4.modules.generic_helpers import _norm_text, _safe_list, get_active_ingredients, has_usable_individual_dose
from scoring_input_contract import classify_ingredient_roles, dose_disclosure_status, is_lent_blend_mass
from scoring_v4.modules.sports_helpers import (
    ALPHA_GPC_CANONICALS,
    ATP_CANONICALS,
    BCAA_AGGREGATE_CANONICALS,
    BCAA_CANONICALS,
    BETA_ALANINE_CANONICALS,
    BETAINE_CANONICALS,
    CAFFEINE_CANONICALS,
    CITRULLINE_CANONICALS,
    CREATINE_CANONICALS,
    EAA_AGGREGATE_CANONICALS,
    EAA_CANONICALS,
    HMB_CANONICALS,
    SPORTS_PROTEIN_CANONICALS,
    TAURINE_CANONICALS,
    canonical,
    group_bcaa,
    group_eaa,
    primary_sports_identity,
    sports_dosed_rows,
    sports_identity_rows,
)


PHASE_MARKER = "P1.7_sports_dose_v1"
METHOD_MARKER = "sports_active_dose_bands_v1"
# Chronic daily references use minimum directed use; acute references stay per use.
_DAILY_CANONICALS = CREATINE_CANONICALS | BETA_ALANINE_CANONICALS | HMB_CANONICALS | BETAINE_CANONICALS

from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "sports")["sports"]


DIMENSION_CAP = _DM["dimension_cap"]


def score_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(product, dict):
        product = {}

    identity, primary, basis, aggregation, scored = _best_primary_score(product)
    not_evaluable = _not_evaluable_reason(product, primary)
    if (
        primary <= 0
        and identity
        and basis
        and not_evaluable == "no_sports_primary_dose"
        and basis != "no_sports_primary_dose"
    ):
        not_evaluable = basis

    components = {
        "sports_primary_active_dose": round(primary, 4),
    }
    # Hidden label amounts use the shared neutral; Transparency B5 owns opacity.
    penalties: Dict[str, float] = {}
    score = _clamp(
        0.0,
        DIMENSION_CAP,
        sum(components.values()) - sum(abs(float(v)) for v in penalties.values()),
    )
    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "method": METHOD_MARKER,
        "primary_identity": identity,
        "dose_basis": basis,
        "dose_aggregation": aggregation,
        "dose_contributions": [_dose_contribution(product, name, points, label)
                               for name, points, label in scored],
        "benchmark_exposures": [
            asdict(row_exposure(product, row, basis="daily" if canonical(row) in _DAILY_CANONICALS else "per_use", unit="g"))
            for row in sports_dosed_rows(product)
            if canonical(row) in _DAILY_CANONICALS | CAFFEINE_CANONICALS
        ],
        "daily_interval_selection": "minimum_directed_use",

    }
    unknown_daily = [e for e in metadata["benchmark_exposures"] if e["benchmark_amount"] is None and e["uncertainty"]]
    if unknown_daily and primary <= 0:
        not_evaluable = unknown_daily[0]["uncertainty"]
    if scored and all(label == "hidden_amount_neutral" for _, _, label in scored):
        not_evaluable = "opaque_primary_sports_blend"
    if not_evaluable:
        metadata["not_evaluable_reason"] = not_evaluable
    # Keep lost source quantities incomplete even when another co-primary has
    # an amount. Protein requires actual Facts grams rather than powder mass.
    unresolved_quantity = any(label and (label.endswith("_no_dose") or label in {"bcaa_incomplete", "eaa_incomplete"})
                              for _, _, label in scored)
    if unresolved_quantity:
        metadata.update(assessment_status="incomplete", reason_code="unresolved_source_quantity")
    return {
        "score": None if unresolved_quantity else round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _score_primary(product: Dict[str, Any], identity: Optional[str], *, details: Optional[dict] = None) -> Tuple[float, Optional[str]]:
    rows = sports_dosed_rows(product)
    canons = next((canons for name, canons in _IDENTITY_CANONICALS if name == identity), frozenset())
    own_rows = [row for row in rows if canonical(row) in canons]
    unit = "mg" if identity in {"alpha_gpc", "atp", "caffeine"} else "g"
    basis = "daily" if identity in {"creatine", "beta_alanine", "hmb", "betaine"} else "per_use"
    if identity == "protein":
        own_rows = _protein_dose_rows(own_rows)
    elif identity == "caffeine":
        from scoring_v4.dose_safety import _declared_caffeine_rows
        own_rows, _bounds, _count = _declared_caffeine_rows(product)
    elif identity == "bcaa":
        grouped = group_bcaa(rows)
        if not grouped["complete"]:
            own_rows = [row for row in sports_identity_rows(product)
                        if canonical(row) in BCAA_AGGREGATE_CANONICALS and not is_lent_blend_mass(row)]
        else:
            own_rows = [{"quantity": grouped["total_g"], "unit": "g"}]
    elif identity == "eaa":
        grouped = group_eaa(rows)
        if grouped["aggregate_total_g"] is None and any(
            canonical(row) in EAA_CANONICALS
            and not is_lent_blend_mass(row)
            and dose_disclosure_status(row) != "not_disclosed_blend"
            and row_exposure(product, row, basis="per_use", unit="g").benchmark_amount is None
            for row in sports_identity_rows(product)
        ):
            return 0.0, "eaa_no_dose"
        if not grouped["complete"] and not grouped["partial"]:
            return 0.0, "eaa_incomplete"
        own_rows = [{"quantity": grouped["total_g"], "unit": "g"}]
    if identity not in {"protein", "bcaa", "eaa", "caffeine"} and any(
        not is_lent_blend_mass(row) and dose_disclosure_status(row) != "not_disclosed_blend"
        and row_exposure(product, row, basis=basis, unit=unit).benchmark_amount is None
        for row in sports_identity_rows(product) if canonical(row) in canons
    ):
        return 0.0, f"{identity}_no_dose"
    amounts = [row_exposure(product, row, basis=basis, unit=unit).benchmark_amount for row in own_rows]
    amounts = [value for value in amounts if value is not None]
    if not amounts or (identity == "caffeine" and len(amounts) != len(own_rows)):
        return 0.0, f"{identity}_no_dose" if identity else "no_sports_primary_dose"

    qualified_rows = own_rows
    qualified = identity in _DM["contribution_targets"]
    if identity == "protein":
        # Reuse the existing source classifier; actual Nutrition Facts mass
        # remains a separate requirement and never becomes powder mass.
        from scoring_v4.modules.sports_formulation import _protein_rows, _source_quality
        _, source = _source_quality(_protein_rows(get_active_ingredients(product)), product)
        qualified = source in {"whey_isolate", "whey_protein", "casein", "soy_protein", "complete_plant_blend"}
    elif identity in {"creatine", "hmb"}:
        qualified_rows = [row for row in own_rows if _qualified_preparation(row, identity)]
        qualified = bool(qualified_rows)
    if qualified:
        from rda_ul_calculator import label_population_members

        # The approved sports references cover adults. A label also aimed at
        # children, pregnancy or lactation cannot borrow that numerical target.
        qualified = not {"pediatric", "pregnancy_lactation"}.intersection(label_population_members(product))
    if not qualified:
        from scoring_v4.modules.generic_helpers import dose_reference_scope, unbenchmarked_dose_credit
        with dose_reference_scope(_primary_dose_reference(product, identity)):
            return unbenchmarked_dose_credit(), f"{identity}_completed_no_general_benchmark"

    amounts = [row_exposure(product, row, basis=basis, unit=unit).benchmark_amount for row in qualified_rows]
    amount = (sum(amounts) if identity == "caffeine" and all(value is not None for value in amounts)
              else max(value for value in amounts if value is not None))
    target = _DM["contribution_targets"][identity]
    if details is not None:
        details.update(reference_value=target, pct_of_reference=100 * amount / target,
                       reference_kind="supplement_contribution_policy", reference_basis=basis)
    return _partial(amount, target, _DM["primary_points"]), f"{identity}_contribution_policy"


def _qualified_preparation(row: Dict[str, Any], identity: str) -> bool:
    """A broad canonical cannot turn an alternate salt into the reviewed form."""
    form = _norm_text(row.get("matched_form") or row.get("form") or row.get("ingredient_form"))
    text = " ".join(_norm_text(row.get(key)) for key in ("name", "raw_source_text", "standard_name"))
    alternate_creatine = ("hydrochloride", "hcl", "nitrate", "citrate", "chelate", "ethyl ester", "buffered")
    if identity == "creatine" and any(term in text for term in alternate_creatine):
        return False
    if form and form != "unspecified":
        text = form
    if "unspecified" in text:
        return False
    if identity == "creatine":
        return "monohydrate" in text and not any(term in text for term in alternate_creatine)
    return any(term in text for term in ("hmb-ca", "hmb-fa", "hmb ca", "hmb fa", "calcium", "free acid"))


_IDENTITY_CANONICALS = (
    ("protein", SPORTS_PROTEIN_CANONICALS), ("creatine", CREATINE_CANONICALS),
    ("beta_alanine", BETA_ALANINE_CANONICALS), ("citrulline", CITRULLINE_CANONICALS),
    ("hmb", HMB_CANONICALS), ("alpha_gpc", ALPHA_GPC_CANONICALS), ("atp", ATP_CANONICALS),
    ("caffeine", CAFFEINE_CANONICALS), ("betaine", BETAINE_CANONICALS), ("taurine", TAURINE_CANONICALS),
    ("bcaa", BCAA_CANONICALS | BCAA_AGGREGATE_CANONICALS),
    ("eaa", EAA_CANONICALS | EAA_AGGREGATE_CANONICALS),
)


def _co_primary_identities(product: Dict[str, Any]) -> list[str]:
    """Source-owned sports purposes, including declared off-list ingredients.

    The shared role owner selects the on-list purposes by materiality.
    Explicit label purpose is required for an off-list ingredient.
    """
    rows = [row for row in get_active_ingredients(product) if isinstance(row, dict)]
    # BCAAs are part of an EAA preparation. Use the existing aggregate owner
    # to choose the preparation once, rather than voting per amino acid or
    # adding a second BCAA vote to a complete/partial EAA profile.
    eaa_group = group_eaa(rows)
    eaa_preparation = (eaa_group["count"] >= 6
                       or eaa_group["aggregate_identity_complete"])
    if not eaa_group["aggregate_identity_complete"]:
        # An untyped EAA header has no verified preparation identity. The
        # aggregate owner must accept it before it can become a purpose vote.
        rows = [row for row in rows if canonical(row) not in EAA_AGGREGATE_CANONICALS]
    group_identity = "eaa" if eaa_preparation else "bcaa"
    group_canons = EAA_CANONICALS if eaa_preparation else BCAA_CANONICALS
    aggregate_canons = EAA_AGGREGATE_CANONICALS if eaa_preparation else BCAA_AGGREGATE_CANONICALS
    group = eaa_group if eaa_preparation else group_bcaa(rows)
    if group["total_g"] > 0 and not any(canonical(row) in aggregate_canons for row in rows):
        # Materiality belongs to the preparation, too. Split amino-acid rows
        # cannot each become a purpose or make a named BCAA/EAA purpose vanish.
        rows = [row for row in rows if canonical(row) not in group_canons]
        rows.append({"canonical_id": next(iter(aggregate_canons)),
                     "name": "Essential Amino Acids EAA" if group_identity == "eaa" else "Branched Chain Amino Acids BCAA",
                     "quantity": group["total_g"], "unit": "g"})
    roles = classify_ingredient_roles(product, module="sports", rows=rows, materiality_only=True)
    found = []
    for row, role in zip(rows, roles):
        if role.get("role") not in {"claim_prominent", "major"}:
            continue
        key = canonical(row)
        identity = next((name for name, canons in _IDENTITY_CANONICALS if key in canons), None)
        if eaa_preparation and key in EAA_CANONICALS | EAA_AGGREGATE_CANONICALS:
            identity = "eaa"
        if identity is None and key and role.get("role") == "claim_prominent":
            # The generic purpose owner excludes structural parent totals.
            # A named container is not another ingredient beside its children;
            # typed on-list preparations retain their aggregate owners above.
            if row.get("is_parent_total"):
                continue
            # Off-list presence or mass alone does not establish a purpose.
            identity = key
        if identity and identity not in found:
            found.append(identity)
    return found


def _best_primary_score(product: Dict[str, Any]) -> Tuple[Optional[str], float, Optional[str], str, list]:
    """Score the product's sports primary (Dose V4.1 \u00a73.2).

    One banded primary from the shared role owner scores against its own
    benchmark; several co-primaries average. Without a role-owned banded
    primary, the dose-supported anchor with the highest credit is used, since
    a fixed canonical priority is unsafe for pre-workouts.
    """
    shared_primary = primary_sports_identity(product)
    co_primaries = [identity for identity in _co_primary_identities(product)
                    if identity != "protein" or shared_primary == "protein"]
    if len(co_primaries) > 1:
        from scoring_v4.modules.generic_helpers import archetype_dose_reference
        from scoring_v4.modules.sports_helpers import sports_subtype

        reference = archetype_dose_reference("sports", module_metadata={"sports_subtype": sports_subtype(product)})
        scored = []
        for identity in co_primaries:
            points, basis = _assess_primary(product, identity)
            own_reference = _primary_dose_reference(product, identity)
            # Normalize each preparation to the common averaging scale once.
            points = min(own_reference, points) / own_reference * reference
            scored.append((identity, points, basis))
        average = sum(score for _, score, _ in scored) / len(scored)
        lead = max(scored, key=lambda item: item[1])
        return lead[0], round(average, 4), lead[2], "co_primary_average", scored
    if co_primaries:
        score, basis = _assess_primary(product, co_primaries[0])
        return co_primaries[0], score, basis, "single_primary", [(co_primaries[0], score, basis)]
    identity, score, basis = _strongest_primary_score(product, shared_primary)
    return identity, score, basis, "strongest_dosed_anchor", ([(identity, score, basis)] if identity else [])


def _strongest_primary_score(product: Dict[str, Any], shared_primary: Optional[str]) -> Tuple[Optional[str], float, Optional[str]]:
    best_identity: Optional[str] = None
    best_score = 0.0
    best_basis: Optional[str] = "no_sports_primary_dose"
    for identity in (
        "protein", "creatine", "bcaa", "eaa", "beta_alanine", "citrulline", "hmb",
        "alpha_gpc", "atp", "caffeine", "betaine", "taurine",
    ):
        # Protein's flat low-amount band must not compete when the shared
        # purpose owner identifies it as an incidental amino-mixture source.
        if identity == "protein" and shared_primary != "protein":
            continue
        score, basis = _assess_primary(product, identity)
        if score > best_score:
            best_identity = identity
            best_score = score
            best_basis = basis
    if best_identity is None:
        fallback_identity = shared_primary
        if fallback_identity:
            _score, basis = _score_primary(product, fallback_identity)
            return fallback_identity, 0.0, basis
    return best_identity, best_score, best_basis


def _assess_primary(product: Dict[str, Any], identity: str) -> Tuple[float, Optional[str]]:
    """Completed source reviews and positively hidden amounts receive neutral."""
    if not any(name == identity for name, _canons in _IDENTITY_CANONICALS):
        entry = _offlist_primary_entry(product, identity)
        return ((float(entry["credit_raw"]), str(entry["assessment"])) if entry is not None
                else (0.0, f"{identity}_no_dose"))
    points, basis = _score_primary(product, identity)
    if points > 0:
        return points, basis
    canons = next(canons for name, canons in _IDENTITY_CANONICALS if name == identity)
    rows = [row for row in sports_identity_rows(product) if canonical(row) in canons]
    if rows and all(is_lent_blend_mass(row) or dose_disclosure_status(row) == "not_disclosed_blend" for row in rows):
        from scoring_v4.modules.generic_helpers import dose_reference_scope, unbenchmarked_dose_credit

        with dose_reference_scope(_primary_dose_reference(product, identity)):
            return unbenchmarked_dose_credit(), "hidden_amount_neutral"
    return points, basis


def _offlist_primary_entry(product: Dict[str, Any], identity: str) -> Optional[dict]:
    """Consume the generic purpose owner's assessment on the sports scale."""
    from scoring_v4.exposure import quantity_is_unresolved
    from scoring_v4.modules.generic_dose import (
        CAP_SUPPLEMENTAL_WINDOW, _product_evidence_dose_credit, _score_declared_purpose_window,
    )
    from scoring_v4.modules.generic_helpers import dose_reference_scope

    rows = [row for row in get_active_ingredients(product) if canonical(row) == identity]
    if not rows or any(quantity_is_unresolved(row) or (
        not has_usable_individual_dose(row) and not is_lent_blend_mass(row)
        and dose_disclosure_status(row) != "not_disclosed_blend"
        and _product_evidence_dose_credit(row)[0] <= 0) for row in rows):
        return None
    # Generic nutritional and clinical calculations retain their own reference;
    # normalize the resulting contribution once, without borrowing their math.
    with dose_reference_scope(CAP_SUPPLEMENTAL_WINDOW):
        entries = _score_declared_purpose_window(product)[-1]
    entry = next((entry for entry in entries if entry.get("ingredient") == identity), None)
    if entry is None:
        return None
    return {**entry, "credit_raw": float(entry["credit_raw"]) / CAP_SUPPLEMENTAL_WINDOW
            * _primary_dose_reference(product, identity)}


def _primary_dose_reference(product: Dict[str, Any], identity: str) -> float:
    """Read the public owner's existing reference for one preparation."""
    from scoring_v4.quality_score import _archetype, _dose_reference
    from scoring_v4.modules.sports_helpers import sports_subtype

    archetype = _archetype("sports", {"metadata": {"sports_subtype": sports_subtype(product)}})
    dimension = {"components": {"sports_primary_active_dose": 0.0},
                 "metadata": {"primary_identity": identity}}
    return _dose_reference(dimension, archetype, _cfg_block("dose_subscale", "archetype_reference"))


def _dose_contribution(product: Dict[str, Any], identity: str, points: float, basis: Optional[str]) -> dict:
    """Project the same source-owned preparation exposure used by the band."""
    result = {"ingredient": identity, "assessment": basis, "credit_raw": round(points, 4)}
    canons = next((canons for name, canons in _IDENTITY_CANONICALS if name == identity), None)
    if canons is None:
        result.update(_offlist_primary_entry(product, identity) or {})
        result["credit_raw"] = round(points, 4)
        canons = frozenset({identity})
        rows = [row for row in get_active_ingredients(product)
                if canonical(row) == identity and has_usable_individual_dose(row)]
    else:
        rows = [row for row in sports_dosed_rows(product) if canonical(row) in canons]
    if identity == "protein":
        rows = _protein_dose_rows(rows)
    if identity == "caffeine":
        from scoring_v4.dose_safety import _declared_caffeine_rows
        rows, _bounds, _count = _declared_caffeine_rows(product)
        amounts = [row_exposure(product, row, basis="per_use", unit="mg").benchmark_amount for row in rows]
        # Sum only a complete declaration, then let the shared exposure owner
        # apply directions to that single analyte total for the receipt.
        if amounts and all(amount is not None for amount in amounts):
            operators = {row_exposure(product, row, basis="per_use", unit="mg").quantity_operator for row in rows}
            rows = [{"quantity": sum(amounts), "unit": "mg",
                     "quantity_operator": next(iter(operators)) if len(operators) == 1 else "unknown"}]
        else:
            rows = []
    if identity in {"creatine", "hmb"} and basis == f"{identity}_contribution_policy":
        rows = [row for row in rows if _qualified_preparation(row, identity)]
    unit = result.get("amount_unit") or ("mg" if identity in {"alpha_gpc", "atp", "caffeine"} else "g")
    if identity in {"bcaa", "eaa"}:
        grouped = group_bcaa(rows) if identity == "bcaa" else group_eaa(rows)
        if identity == "bcaa" and not grouped["complete"]:
            rows = [row for row in sports_identity_rows(product)
                    if canonical(row) in BCAA_AGGREGATE_CANONICALS and not is_lent_blend_mass(row)]
        elif identity == "eaa" and grouped["aggregate_total_g"] is not None:
            rows = [row for row in rows if canonical(row) in EAA_AGGREGATE_CANONICALS]
        else:
            # Collapse amino acid components through their aggregate owner,
            # then apply the shared exposure owner to that one preparation.
            total = grouped["total_g"]
            rows = [{"quantity": total, "unit": "g"}] if total > 0 else []
    basis_kind = "per_use" if any(name == identity for name, _ in _IDENTITY_CANONICALS) and identity not in {"creatine", "beta_alanine", "hmb", "betaine"} else "daily"
    exposures = [(row, row_exposure(product, row, basis=basis_kind, unit=unit)) for row in rows]
    usable = [(row, exposure) for row, exposure in exposures if exposure.benchmark_amount is not None]
    if usable:
        row, benchmark = max(usable, key=lambda pair: pair[1].benchmark_amount)
        daily = row_exposure(product, row, basis="daily", unit=unit)
        result.update(amount_per_serving=benchmark.per_serving_amount,
                      amount_at_minimum=daily.benchmark_amount,
                      amount_at_maximum=daily.benchmark_maximum, amount_unit=unit,
                      quantity_operator=daily.quantity_operator,
                      frequency_defaulted=daily.frequency_defaulted)
        if basis == f"{identity}_contribution_policy":
            _score_primary(product, identity, details=result)
    return result


def _not_evaluable_reason(product: Dict[str, Any], primary_score: float) -> Optional[str]:
    if primary_score > 0:
        return None
    blends = [b for b in _safe_list((product or {}).get("proprietary_blends")) if isinstance(b, dict)]
    if any(_norm_text(blend.get("disclosure_level")) in {"none", "partial", ""} for blend in blends):
        return "opaque_primary_sports_blend"
    return "no_sports_primary_dose"


def _protein_dose_rows(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Use the input contract's actual-protein projection, never powder mass."""
    return [row for row in rows if canonical(row) == "protein"
            and _norm_text(row.get("scoring_input_kind")) == "product_level_evidence"
            and _norm_text(row.get("evidence_type")) == "sports_primary_dose"
            and row.get("reason") == "declared_nutrition_protein_mass"]


def _partial(value: float, target: float, max_points: float) -> float:
    if target <= 0:
        return 0.0
    return _clamp(0.0, max_points, (value / target) * max_points)


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))
