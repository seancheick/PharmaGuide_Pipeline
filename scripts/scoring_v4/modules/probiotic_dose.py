"""v4 Probiotic Dose dimension — P2.2.

Scores probiotic dose quality against the 25-point rubric in
SCORING_V4_PROPOSAL §6:

  - per-strain CFU disclosure: 10
  - measured CFU potency: 15, using the existing physical potency bands
    without importing clinical citation approval or evidence strength

Aggregate CFU is not treated as per-strain disclosure. When named strains and
a total CFU are present but strain-level CFU is absent, only the existing limited
total-disclosure floor applies. Unknown blend shares are never allocated equally.

A reviewed complete-formula dose instead owns the full dimension: unknown
individual allocations cannot invalidate an assessed formula-level dose.
Individual allocation disclosure remains separately visible in Transparency.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Set

from scoring_input_contract import get_scoring_ingredients
from probiotic_measurements import (
    AFU_REVIEW_REASON, pending_afu_measurements, normalized_cfu_count, declared_total_cfu,
)


PHASE_MARKER = "P2.2_probiotic_dose"
from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "probiotic")["probiotic"]


CAP_DOSE = _DM["cap_dose"]
CAP_PER_STRAIN_CFU_DISCLOSURE = _DM["cap_per_strain_cfu_disclosure"]
CAP_CFU_ADEQUACY = _DM["cap_cfu_adequacy"]
AGGREGATE_CFU_LOW_TIER_PRESENCE_FLOOR = _DM["aggregate_cfu_low_tier_presence_floor"]
AGGREGATE_CFU_LOW_NAMED_STRAIN_TOTAL_FLOOR = _DM["aggregate_cfu_low_named_strain_total_floor"]
# A named strain disclosed at its OWN mass (e.g. BB536 25 mg) with no CFU gets a
# small disclosure floor. It is not a conversion from mass to viable count.
CAP_DIRECT_STRAIN_MASS_FLOOR = _DM["cap_direct_strain_mass_floor"]
# Rows whose NAME marks them as a blend/header/container, not a single strain at a
# disclosed mass. The floor must never fire on these (opacity is not rewarded).
_BLEND_ROW_RE = re.compile(
    r"\b(blend|proprietary|complex|matrix|formula|formulation|cultures?|"
    r"prebiotic|probiotic\s+blend|bacteria)\b",
    re.IGNORECASE,
)
_MASS_UNITS = frozenset({"mg", "milligram", "milligrams", "g", "gram", "grams", "gm",
                         "mcg", "microgram", "micrograms", "ug", "µg"})
V3_CFU_ADEQUACY_CAP = _DM["v3_cfu_adequacy_cap"]

TIER_POINTS = dict(_DM["tier_points"])


def score_dose(product: Any) -> Dict[str, Any]:
    """Return the probiotic Dose dimension payload.

    Per-strain disclosure is proportional to the number of named strains
    with an individual CFU value. Physical potency uses source-owned daily
    measurements and the existing /5 to /15 scaling, not clinical review flags.
    """
    product = product if isinstance(product, dict) else {}
    from studied_formulas import (
        assess_studied_formula, label_owned_native_strains, measured_native_strain_doses,
    )
    if not product.get("probiotic_data") and isinstance(product.get("probiotic_detail"), dict):
        product = {**product, "probiotic_data": product["probiotic_detail"]}
    formula = assess_studied_formula(product)
    if formula["status"] == "assessed_studied_formula":
        return {
            "score": CAP_DOSE, "max": CAP_DOSE,
            "components": {"studied_formula_dose_adequacy": CAP_DOSE},
            "penalties": {},
            "metadata": {"phase": PHASE_MARKER, "assessment_status": formula["status"],
                         "dose_adequacy_basis": "studied_formula_native_afu",
                         "studied_formula_assessment": formula,
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
            },
        }
    pdata = _probiotic_payload(product)
    clinical_strains = label_owned_native_strains(product)
    measured_strains = measured_native_strain_doses(product)

    total_strain_count = _total_strain_count(pdata, clinical_strains)
    disclosed_keys = _per_strain_cfu_disclosed_keys(pdata, clinical_strains)
    disclosed_count = min(len(disclosed_keys), total_strain_count) if total_strain_count else 0
    disclosure_score = _score_per_strain_cfu_disclosure(disclosed_count, total_strain_count)

    adequacy = _compute_cfu_adequacy(measured_strains)
    cfu_adequacy_v3 = adequacy["v3_points"]
    cfu_adequacy_scaled = min(CAP_CFU_ADEQUACY, cfu_adequacy_v3 * 3.0)
    aggregate_proxy = _compute_aggregate_cfu_proxy(
        pdata,
        clinical_strains,
        total_strain_count=total_strain_count,
        disclosed_count=disclosed_count,
    )
    aggregate_proxy["applied"] = aggregate_proxy["score"] > cfu_adequacy_scaled
    if aggregate_proxy["applied"]:
        cfu_adequacy_scaled = aggregate_proxy["score"]
    # Direct per-strain mass floor: a named strain disclosed at its OWN mass (e.g.
    # BB536 25 mg) with no CFU is not "no dose disclosed". Give a conservative floor
    # so dose isn't treated as fully absent. This is not viable-count adequacy.
    # Never fires for proprietary-blend mass — opacity is not rewarded.
    direct_strain_mass_floor = _compute_direct_strain_mass_floor(product, clinical_strains)
    # Only when NO per-strain CFU is disclosed (disclosed_count == 0) AND adequacy is
    # otherwise 0. A product that discloses per-strain CFU already has its dose
    # assessed — mass must not stack a floor on top of real CFU disclosure.
    if (
        disclosed_count == 0
        and cfu_adequacy_scaled <= 0.0
        and direct_strain_mass_floor["score"] > 0.0
    ):
        cfu_adequacy_scaled = direct_strain_mass_floor["score"]
        direct_strain_mass_floor["applied"] = True
    cfu_adequacy_basis = _cfu_adequacy_basis(
        cfu_adequacy_scaled,
        aggregate_proxy,
        direct_strain_mass_floor,
        disclosed_count=disclosed_count,
    )
    cfu_guarantee = _cfu_guarantee_adjustment(pdata)
    if (
        cfu_adequacy_scaled > 0.0
        and cfu_guarantee["multiplier"] < 1.0
        and cfu_adequacy_basis != "direct_strain_mass_no_cfu_floor"
    ):
        cfu_adequacy_scaled *= cfu_guarantee["multiplier"]
        cfu_guarantee["applied"] = True
        cfu_guarantee["adjusted_score"] = round(cfu_adequacy_scaled, 4)
    cfu_adequacy_basis = _cfu_adequacy_basis(
        cfu_adequacy_scaled,
        aggregate_proxy,
        direct_strain_mass_floor,
        disclosed_count=disclosed_count,
    )

    components = {
        "per_strain_cfu_disclosure": round(disclosure_score, 2),
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
            "raw_score": round(raw_score, 4),
            "total_strain_count": total_strain_count,
            "per_strain_cfu_disclosed_count": disclosed_count,
            "cfu_adequacy_v3_points": round(cfu_adequacy_v3, 4),
            "cfu_adequacy_scaled_points": round(cfu_adequacy_scaled, 4),
            "cfu_adequacy_basis": cfu_adequacy_basis,
            "reference_basis": "industry_potency_not_trial_efficacy",
            "cfu_adequacy_contributions": adequacy["strain_contributions"],
            "aggregate_cfu_proxy": aggregate_proxy,
            "direct_strain_mass_floor": direct_strain_mass_floor,
            "cfu_guarantee": cfu_guarantee,
            "window_proxy_reason": _disclosure_reason(pdata, total_strain_count, disclosed_count),
        },
    }


def _compute_cfu_adequacy(clinical_strains: Iterable[Any]) -> Dict[str, Any]:
    contributions: List[Dict[str, Any]] = []
    total = 0.0

    for item in clinical_strains or []:
        strain = _safe_dict(item)
        if not strain:
            continue

        tier = _norm(strain.get("adequacy_tier"))
        cfu = _as_float(strain.get("cfu_per_day"), None)

        if strain.get("is_inactivated") or strain.get("is_postbiotic"):
            contributions.append({
                "tier": tier or strain.get("adequacy_tier"),
                "cfu_per_day": cfu,
                "points": 0.0,
                "skipped_reason": "postbiotic_inactivated_no_cfu_credit",
            })
            continue

        if tier is None or cfu is None or cfu <= 0:
            contributions.append({
                "tier": tier or strain.get("adequacy_tier"),
                "cfu_per_day": cfu,
                "points": 0.0,
            })
            continue

        points = TIER_POINTS.get(tier, 0.0)
        total += points
        contributions.append({
            "tier": tier,
            "clinical_id": strain.get("clinical_id"),
            "source_row_ref": strain.get("source_row_ref"),
            "cfu_per_day": cfu,
            "maximum_cfu_per_day": strain.get("maximum_cfu_per_day"),
            "exposure_basis": "minimum_daily_servings",
            "points": round(points, 4),
        })

    total = min(V3_CFU_ADEQUACY_CAP, total)
    return {
        "v3_points": total,
        "strain_contributions": contributions,
    }


def _cfu_adequacy_basis(
    cfu_adequacy_scaled: float,
    aggregate_proxy: Dict[str, Any],
    direct_strain_mass_floor: Dict[str, Any],
    *,
    disclosed_count: int,
) -> str:
    if aggregate_proxy.get("applied"):
        return "aggregate_cfu_disclosed_only"
    if direct_strain_mass_floor.get("applied"):
        return "direct_strain_mass_no_cfu_floor"
    if cfu_adequacy_scaled > 0.0 and disclosed_count > 0:
        return "per_strain_cfu_disclosed"
    if cfu_adequacy_scaled > 0.0:
        return "strain_level_cfu_evidence"
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
            "multiplier": 0.9,
            "applied": False,
            "reason": "cfu_guaranteed_at_manufacture",
        }
    return {
        "type": "unknown",
        "multiplier": 0.85,
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
        row.get("is_in_proprietary_blend")
        or row.get("is_proprietary_blend")
        or row.get("is_blend_header")
        or row.get("is_blend")
        or row.get("is_parent_total")
    ):
        return True
    if row.get("scoring_input_kind") == "product_level_evidence":
        return True
    if _norm(row.get("evidence_type")) in {"blend_anchor_mass", "conservative_blend_anchor_mass"}:
        return True
    role = _norm(row.get("role") or row.get("cleaner_role") or row.get("scoring_input_kind"))
    if role in {"blend_header_total", "nested_display_only", "composition_leaf"}:
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
    """Conservative dose floor for a named strain disclosed at its OWN mass with no
    CFU (Bifido BB536 25 mg). Matches a clinical strain to an ingredient row that
    (a) carries that strain's name, (b) has a positive disclosed mass, and (c) is
    NOT a blend/header row. Never fires for proprietary-blend mass. Payload is
    shaped like the aggregate-CFU proxy."""
    payload: Dict[str, Any] = {
        "applied": False,
        "score": 0.0,
        "cap": CAP_DIRECT_STRAIN_MASS_FLOOR,
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
        payload["score"] = CAP_DIRECT_STRAIN_MASS_FLOOR
        payload["reason"] = "direct_strain_mass_no_cfu"
        payload["matched_strains"] = matched
    else:
        payload["reason"] = "no_direct_strain_mass_match"
    return payload


def _compute_aggregate_cfu_proxy(
    pdata: Dict[str, Any],
    clinical_strains: Iterable[Any],
    *,
    total_strain_count: int,
    disclosed_count: int,
) -> Dict[str, Any]:
    """Limited total-disclosure credit; never invent per-strain allocations.

    Keep the existing two presence floors. Neither is a clinical dose claim;
    the equal-split model and source-strength multiplier have no label basis.
    """
    payload = {
        "applied": False,
        "score": 0.0,
        "cap": AGGREGATE_CFU_LOW_NAMED_STRAIN_TOTAL_FLOOR,
        "reason": None,
    }
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

    strains = [_safe_dict(item) for item in clinical_strains or []]
    live_strains = [
        strain for strain in strains
        if strain and not strain.get("is_inactivated") and not strain.get("is_postbiotic")
    ]
    if not live_strains:
        payload.update({
            "applied": True,
            "score": AGGREGATE_CFU_LOW_TIER_PRESENCE_FLOOR,
            "reason": "aggregate_cfu_label_presence",
            "total_billion_count": round(total_billion, 4),
            "floor": AGGREGATE_CFU_LOW_TIER_PRESENCE_FLOOR,
        })
        return payload

    score = (AGGREGATE_CFU_LOW_NAMED_STRAIN_TOTAL_FLOOR if total_billion >= 1.0
             else AGGREGATE_CFU_LOW_TIER_PRESENCE_FLOOR)
    payload.update({
        "applied": score > 0.0,
        "score": round(score, 4),
        "reason": "aggregate_cfu_named_label_presence" if total_billion >= 1.0 else "aggregate_cfu_label_presence",
        "total_billion_count": round(total_billion, 4),
        "floor": score,
    })
    return payload


def _score_per_strain_cfu_disclosure(disclosed_count: int, total_strain_count: int) -> float:
    if total_strain_count <= 0 or disclosed_count <= 0:
        return 0.0
    ratio = min(1.0, disclosed_count / total_strain_count)
    return CAP_PER_STRAIN_CFU_DISCLOSURE * ratio


def _per_strain_cfu_disclosed_keys(
    pdata: Dict[str, Any],
    clinical_strains: Iterable[Any],
) -> Set[str]:
    keys: Set[str] = set()

    # Disclosure is a property of the label measurement, not a clinical-match
    # stamp. A stale cfu_per_day cannot manufacture disclosed quantities.
    for blend_item in _safe_list(pdata.get("probiotic_blends")):
        blend = _safe_dict(blend_item)
        strains = [str(s).strip() for s in _safe_list(blend.get("strains")) if str(s).strip()]
        if len(strains) != 1:
            continue
        cfu_data = _safe_dict(blend.get("cfu_data"))
        if (cfu_data.get("evidence_scope") not in {None, "row_level"}
                or (cfu_data.get("raw_source_path") is not None
                    and cfu_data["raw_source_path"] != blend.get("raw_source_path"))):
            continue
        if _cfu_data_has_individual_cfu(cfu_data):
            keys.add(_canonical_key(strains[0]))

    return {key for key in keys if key}


def _cfu_data_has_individual_cfu(cfu_data: Dict[str, Any]) -> bool:
    if cfu_data.get("has_cfu") is not True:
        return False
    # A parser flag without a finite positive amount is not dose disclosure.
    return normalized_cfu_count(cfu_data) is not None


def _total_strain_count(pdata: Dict[str, Any], clinical_strains: Iterable[Any]) -> int:
    declared = _as_int(pdata.get("total_strain_count"), 0)
    if declared > 0:
        return declared

    seen: Set[str] = set()
    for blend_item in _safe_list(pdata.get("probiotic_blends")):
        blend = _safe_dict(blend_item)
        for strain in _safe_list(blend.get("strains")):
            key = _canonical_key(str(strain))
            if key:
                seen.add(key)
    # Clinical IDs and label names are not interchangeable counting keys.
    return len(seen) or len({s.get("clinical_id") for s in clinical_strains if s.get("clinical_id")})


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


def _canonical_key(value: str) -> str:
    text = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


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


def _as_int(value: Any, default: int = 0) -> int:
    return int(_as_float(value, default))


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower()
