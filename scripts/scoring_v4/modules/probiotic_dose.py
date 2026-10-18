"""v4 Probiotic Dose dimension — P2.2.

Without an applicable exact studied formula, each strain contributes the shared
completed neutral. Historical CFU tiers and guarantee types remain descriptive
label facts and never establish a monotonic clinical Dose curve. Unknown blend
shares are never allocated equally; disclosure remains in Transparency.

The existing exact complete-formula policy owns its qualified full Dose award.
Unresolved CFU capture, AFU references and material identity/preparation holds
remain incomplete; completed general no-benchmark conclusions are distinct.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List

from scoring_input_contract import get_scoring_ingredients
from probiotic_measurements import (
    AFU_REVIEW_REASON, pending_afu_measurements, declared_total_cfu,
    probiotic_label_identity_summary, unresolved_cfu_measurements,
)
from scoring_v4.modules.generic_helpers import (
    archetype_dose_reference, dose_reference_scope, unbenchmarked_dose_credit,
)


PHASE_MARKER = "P2.2_probiotic_dose"
from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "probiotic")["probiotic"]


CAP_DOSE = _DM["cap_dose"]
CAP_CFU_ADEQUACY = _DM["cap_cfu_adequacy"]
# Rows whose NAME marks them as a blend/header/container, not a single strain at a
# disclosed mass. A blend mass is never read as one strain's own mass.
_BLEND_ROW_RE = re.compile(
    r"\b(blend|proprietary|complex|matrix|formula|formulation|cultures?|"
    r"prebiotic|probiotic\s+blend|bacteria)\b",
    re.IGNORECASE,
)
_MASS_UNITS = frozenset({"mg", "milligram", "milligrams", "g", "gram", "grams", "gm",
                         "mcg", "microgram", "micrograms", "ug", "µg"})
V3_CFU_ADEQUACY_CAP = _DM["v3_cfu_adequacy_cap"]


def score_dose(product: Any) -> Dict[str, Any]:
    """Return the probiotic Dose dimension payload.

    Exact formulas use their existing qualification. General strain assessments
    use the completed neutral while retaining measurements and disclosure facts.
    """
    product = product if isinstance(product, dict) else {}
    from studied_formulas import (
        assess_probiotic_evidence, label_owned_native_strains, measured_native_strain_doses,
    )
    if not product.get("probiotic_data") and isinstance(product.get("probiotic_detail"), dict):
        product = {**product, "probiotic_data": product["probiotic_detail"]}
    unresolved = unresolved_cfu_measurements(product)
    if unresolved:
        return {"score": None, "max": CAP_DOSE, "components": {}, "penalties": {},
                "metadata": {"phase": PHASE_MARKER, "assessment_status": "incomplete",
                             "reason_code": "unresolved_source_quantity", "measurements": unresolved}}
    assessment = assess_probiotic_evidence(product)
    formula = assessment["formula_assessment"]
    if formula["status"] == "assessed_studied_formula":
        return {
            "score": CAP_DOSE, "max": CAP_DOSE,
            "components": {"studied_formula_dose_adequacy": CAP_DOSE},
            "penalties": {},
            "metadata": {"phase": PHASE_MARKER, "assessment_status": formula["status"],
                         "dose_adequacy_basis": "studied_formula_native_afu",
                         "studied_formula_assessment": formula,
                         "evidence_assessment": assessment,
                         "per_strain_cfu_disclosed_count": 0,
                         "window_proxy_reason": "formula_dose_not_individual_strain_doses"},
        }
    afu_rows = pending_afu_measurements(product)
    if afu_rows:
        return {
            "score": None,
            "max": CAP_DOSE,
            "components": {},
            "penalties": {},
            "metadata": {
                "phase": PHASE_MARKER,
                "assessment_status": "unresolved_reference",
                "reason_code": AFU_REVIEW_REASON,
                "afu_measurements": afu_rows,
                "studied_formula_assessment": formula,
                "evidence_assessment": assessment,
            },
        }
    pdata = _probiotic_payload(product)
    clinical_strains = label_owned_native_strains(product)
    measured_strains = measured_native_strain_doses(product)

    identities = probiotic_label_identity_summary(product)
    total_strain_count = identities["total_strain_count"]
    disclosed_count = identities["per_strain_cfu_disclosed_count"]

    cfu_guarantee = _cfu_guarantee_adjustment(pdata)
    with dose_reference_scope(archetype_dose_reference("probiotic")):
        neutral_v3 = unbenchmarked_dose_credit() / 3.0
    adequacy = _compute_cfu_adequacy(measured_strains, total_strain_count=total_strain_count,
                                     neutral_v3=neutral_v3, guarantee=cfu_guarantee)
    cfu_adequacy_v3 = adequacy["v3_points"]
    cfu_adequacy_scaled = min(CAP_CFU_ADEQUACY, cfu_adequacy_v3 * 3.0)
    # V4.1 Step 4: a total CFU count, or a named strain at its own mass with no
    # CFU (BB536 25 mg), is a label limitation rather than demonstrated
    # adequacy. Both are recorded for the explanation and earn no Dose credit;
    # they never replace a measured strain's adequacy.
    # "applied" marks the limitation that explains the Dose basis: only when
    # no strain was measured, and a disclosed total CFU takes precedence.
    measured = any((_as_float(_safe_dict(strain).get("cfu_per_day"), 0.0) or 0.0) > 0
                   for strain in measured_strains) or disclosed_count > 0
    aggregate_proxy = _compute_aggregate_cfu_proxy(
        pdata,
        total_strain_count=total_strain_count,
        disclosed_count=disclosed_count,
    )
    aggregate_proxy["applied"] = aggregate_proxy["applied"] and not measured
    direct_strain_mass_floor = _compute_direct_strain_mass_floor(product, clinical_strains)
    direct_strain_mass_floor["applied"] = bool(
        disclosed_count == 0 and direct_strain_mass_floor["matched_strains"]
        and not measured and not aggregate_proxy["applied"]
    )
    cfu_adequacy_basis = _cfu_adequacy_basis(
        adequacy,
        aggregate_proxy,
        direct_strain_mass_floor,
        disclosed_count=disclosed_count,
    )

    components = {
        "cfu_adequacy": round(cfu_adequacy_scaled, 2),
    }
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_DOSE, raw_score))

    return {
        "score": round(score, 2),
        "max": CAP_DOSE,
        "components": components,
        "penalties": {},
        "metadata": {
            "phase": PHASE_MARKER,
            "studied_formula_assessment": formula,
            "evidence_assessment": assessment,
            "raw_score": round(raw_score, 4),
            "total_strain_count": total_strain_count,
            "per_strain_cfu_disclosed_count": disclosed_count,
            "cfu_adequacy_v3_points": round(cfu_adequacy_v3, 4),
            "cfu_adequacy_scaled_points": round(cfu_adequacy_scaled, 4),
            "cfu_adequacy_basis": cfu_adequacy_basis,
            "reference_basis": "completed_no_general_strain_benchmark",
            "cfu_adequacy_contributions": adequacy["strain_contributions"],
            "dose_aggregation": "strain_average_with_neutral_states",
            "strain_assessment_count": adequacy["assessment_count"],
            "strain_measured_count": adequacy["measured_count"],
            "strain_neutral_count": adequacy["neutral_count"],
            "aggregate_cfu_proxy": aggregate_proxy,
            "direct_strain_mass_floor": direct_strain_mass_floor,
            "cfu_guarantee": cfu_guarantee,
            "window_proxy_reason": _disclosure_reason(pdata, total_strain_count, disclosed_count),
        },
    }


def _compute_cfu_adequacy(clinical_strains: Iterable[Any], *, total_strain_count: int = 0,
                          neutral_v3: float | None = None, guarantee: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Average the label's strain assessments (Dose V4.1 §3.2).

    Reviewed clinical counts and guarantee types describe the label. They do
    not establish increasing clinical adequacy tiers. Each completed general
    strain assessment takes the shared neutral; exact formulas are handled by
    the qualified formula owner before this helper.
    """
    if neutral_v3 is None:
        with dose_reference_scope(archetype_dose_reference("probiotic")):
            neutral_v3 = unbenchmarked_dose_credit() / 3.0
    contributions: List[Dict[str, Any]] = []

    for item in clinical_strains or []:
        strain = _safe_dict(item)
        if not strain:
            continue

        tier = _norm(strain.get("adequacy_tier"))
        cfu = _as_float(strain.get("cfu_per_day"), None)

        if strain.get("is_inactivated") or strain.get("is_postbiotic"):
            contributions.append({
                "strain": strain.get("strain"),
                "tier": tier or strain.get("adequacy_tier"),
                "cfu_per_day": cfu,
                "points": round(neutral_v3, 4),
                "state": "neutral_no_live_count_reference",
            })
            continue

        if tier is None or cfu is None or cfu <= 0:
            contributions.append({
                "strain": strain.get("strain"),
                "tier": tier or strain.get("adequacy_tier"),
                "cfu_per_day": cfu,
                "points": round(neutral_v3, 4),
                "state": "neutral_amount_not_disclosed" if cfu is None or cfu <= 0 else "neutral_no_strain_benchmark",
            })
            continue

        # Counts and historical potency tiers remain descriptive. No reviewed
        # strain source establishes a monotonic clinical Dose tier curve.
        contributions.append({
            "state": "neutral_no_strain_benchmark",
            "strain": strain.get("strain"), "tier": tier,
            "clinical_id": strain.get("clinical_id"),
            "source_row_ref": strain.get("source_row_ref"),
            "cfu_per_day": cfu,
            "maximum_cfu_per_day": strain.get("maximum_cfu_per_day"),
            "exposure_basis": "minimum_daily_servings",
            "points": round(neutral_v3, 4),
        })

    for _ in range(max(0, int(total_strain_count or 0) - len(contributions))):
        contributions.append({"tier": None, "cfu_per_day": None, "points": round(neutral_v3, 4),
                              "state": "neutral_no_strain_benchmark"})
    measured = sum(1 for item in contributions if item["state"] == "measured")
    average = (sum(item["points"] for item in contributions) / len(contributions)) if contributions else 0.0
    return {
        "v3_points": round(min(V3_CFU_ADEQUACY_CAP, average), 4),
        "strain_contributions": contributions,
        "assessment_count": len(contributions),
        "measured_count": measured,
        "neutral_count": len(contributions) - measured,
    }


def _cfu_adequacy_basis(
    adequacy: Dict[str, Any],
    aggregate_proxy: Dict[str, Any],
    direct_strain_mass_floor: Dict[str, Any],
    *,
    disclosed_count: int,
) -> str:
    if disclosed_count > 0:
        return "per_strain_cfu_disclosed"
    if adequacy["measured_count"]:
        return "strain_level_cfu_evidence"
    if aggregate_proxy.get("applied"):
        return "aggregate_cfu_disclosed_only"
    if direct_strain_mass_floor.get("applied"):
        return "direct_strain_mass_no_cfu_floor"
    return "no_cfu_adequacy_credit"


def _cfu_guarantee_adjustment(pdata: Dict[str, Any]) -> Dict[str, Any]:
    guarantee = _norm(pdata.get("guarantee_type")) or "unknown"
    if guarantee in {
        "at_expiration",
        "until_expiration",
        "through_expiration",
        "guaranteed_through_expiration",
        "expiration",
    }:
        return {
            "type": "at_expiration",
            "multiplier": 1.0,
            "applied": False,
            "reason": "cfu_guaranteed_through_expiration",
        }
    if guarantee in {"at_manufacture", "manufacture", "time_of_manufacture"}:
        return {
            "type": "at_manufacture",
            "multiplier": 1.0,
            "applied": False,
            "reason": "cfu_guaranteed_at_manufacture",
        }
    return {
        "type": "unknown",
        "multiplier": 1.0,
        "applied": False,
        "reason": "cfu_guarantee_not_disclosed",
    }


def _ingredient_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return [
            row for row in get_scoring_ingredients(product or {}, strict=True).rows
            if isinstance(row, dict)
        ]
    except Exception:
        return []


def _row_is_blend_header(row: Dict[str, Any]) -> bool:
    if (
        row.get("is_proprietary_blend")
        or row.get("is_blend_header")
        or row.get("is_parent_total")
    ):
        return True
    if row.get("scoring_input_kind") == "product_level_evidence":
        return True
    if _norm(row.get("evidence_type")) in {"blend_anchor_mass", "conservative_blend_anchor_mass"}:
        return True
    text = " ".join(
        str(row.get(key) or "")
        for key in ("name", "standardName", "standard_name", "raw_source_text", "display_label")
    )
    return bool(_BLEND_ROW_RE.search(text))


def _row_positive_mass(row: Dict[str, Any]) -> bool:
    quantity = None
    for key in ("quantity", "amount", "dose", "dosage"):
        quantity = _as_float(row.get(key), None)
        if quantity is not None:
            break
    unit = _norm(row.get("unit_normalized") or row.get("unit") or row.get("dose_unit"))
    return quantity is not None and quantity > 0 and unit in _MASS_UNITS


def _compute_direct_strain_mass_floor(
    product: Dict[str, Any],
    clinical_strains: Iterable[Any],
) -> Dict[str, Any]:
    """Record a named strain disclosed at its OWN mass with no CFU (Bifido BB536
    25 mg): a row that (a) carries that strain's name, (b) has a positive
    disclosed mass, and (c) is NOT a blend/header row. A label limitation for
    the explanation; mass is never converted to a viable count."""
    payload: Dict[str, Any] = {
        "applied": False,
        "reason": None,
        "matched_strains": [],
        "excluded_blend_rows": [],
    }
    strains = [_safe_dict(s) for s in (clinical_strains or [])]
    strains = [s for s in strains if s and not s.get("is_inactivated") and not s.get("is_postbiotic")]
    if not strains:
        payload["reason"] = "no_named_strains"
        return payload

    from studied_formulas import clinical_strain_matches_source_row
    matched: List[str] = []
    for row in _ingredient_rows(product):
        name = str(
            row.get("name")
            or row.get("standardName")
            or row.get("standard_name")
            or row.get("raw_source_text")
            or ""
        )
        if _row_is_blend_header(row):
            if name:
                payload["excluded_blend_rows"].append(name[:48])
            continue
        if not _row_positive_mass(row):
            continue
        if any(clinical_strain_matches_source_row(product, strain, row) for strain in strains):
            matched.append(name[:48])

    if matched:
        payload["reason"] = "direct_strain_mass_no_cfu"
        payload["matched_strains"] = matched
    else:
        payload["reason"] = "no_direct_strain_mass_match"
    return payload


def _compute_aggregate_cfu_proxy(
    pdata: Dict[str, Any],
    *,
    total_strain_count: int,
    disclosed_count: int,
) -> Dict[str, Any]:
    """Record a total CFU disclosed without every strain's own CFU.

    A label limitation for the explanation, never a per-strain allocation or
    an efficacy claim: NIH ODS states that higher CFU counts do not necessarily
    provide greater health benefits.
    """
    payload: Dict[str, Any] = {"applied": False, "reason": None}
    if disclosed_count >= total_strain_count:
        payload["reason"] = "full_per_strain_cfu_present"
        return payload
    if total_strain_count <= 0:
        payload["reason"] = "no_strain_data"
        return payload

    total_billion = _total_billion_count(pdata)
    if total_billion <= 0.0:
        payload["reason"] = "aggregate_cfu_missing"
        return payload

    payload.update({
        "applied": True,
        "reason": "aggregate_cfu_label_presence",
        "total_billion_count": round(total_billion, 4),
    })
    return payload


def _disclosure_reason(pdata: Dict[str, Any], total_strain_count: int, disclosed_count: int) -> str | None:
    if disclosed_count > 0:
        return None
    if total_strain_count <= 0:
        return "no_strain_data"
    if declared_total_cfu(pdata) > 0:
        return "aggregate_cfu_not_per_strain"
    return "per_strain_cfu_missing"


def _total_billion_count(pdata: Dict[str, Any]) -> float:
    return declared_total_cfu(pdata) / 1e9


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    """Read enriched-input `probiotic_data` and final-blob `probiotic_detail`."""
    return _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower()
