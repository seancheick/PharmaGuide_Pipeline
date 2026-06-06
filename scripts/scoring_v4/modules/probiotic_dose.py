"""v4 Probiotic Dose dimension — P2.2.

Scores probiotic dose quality against the 25-point rubric in
SCORING_V4_PROPOSAL §6:

  - per-strain CFU disclosure: 10
  - CFU adequacy: 15, preserving v3's tier × support-level math and
    scaling the v3 5-point cap to the v4 15-point budget

Aggregate CFU is not treated as per-strain disclosure. When named strains and
a total CFU are present but strain-level CFU is absent, the module grants only
a capped adequacy proxy and keeps the disclosure/confidence caveat. This avoids
turning real dose evidence into zero while still penalizing the label gap.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set


PHASE_MARKER = "P2.2_probiotic_dose"
CAP_DOSE = 25.0
CAP_PER_STRAIN_CFU_DISCLOSURE = 10.0
CAP_CFU_ADEQUACY = 15.0
CAP_AGGREGATE_CFU_PROXY_ADEQUACY = 8.0
# A named strain disclosed at its OWN mass (e.g. BB536 25 mg) with no CFU gets a
# small dose floor — strictly below the aggregate-CFU proxy, since mass is a weaker
# potency signal than CFU and must not approach real CFU credit.
CAP_DIRECT_STRAIN_MASS_FLOOR = 5.0
# Rows whose NAME marks them as a blend/header/container, not a single strain at a
# disclosed mass. The floor must never fire on these (opacity is not rewarded).
_BLEND_ROW_RE = re.compile(
    r"\b(blend|proprietary|complex|matrix|formula|formulation|cultures?|"
    r"prebiotic|probiotic\s+blend|bacteria)\b",
    re.IGNORECASE,
)
_MASS_UNITS = frozenset({"mg", "milligram", "milligrams", "g", "gram", "grams", "gm",
                         "mcg", "microgram", "micrograms", "ug", "µg"})
V3_CFU_ADEQUACY_CAP = 5.0

TIER_POINTS = {
    "low": 0.0,
    "adequate": 1.0,
    "good": 2.0,
    "excellent": 3.0,
}

SUPPORT_LEVEL_CAPS = {
    "high": 1.0,
    "moderate": 0.75,
    "weak": 0.5,
}


def score_dose(product: Any) -> Dict[str, Any]:
    """Return the probiotic Dose dimension payload.

    Per-strain disclosure is proportional to the number of named strains
    with an individual CFU value. CFU adequacy mirrors v3's
    `_compute_probiotic_cfu_adequacy_points` arithmetic, then scales the
    capped v3 total from /5 to /15.
    """
    product = product if isinstance(product, dict) else {}
    pdata = _probiotic_payload(product)
    clinical_strains = _safe_list(pdata.get("clinical_strains"))

    total_strain_count = _total_strain_count(pdata, clinical_strains)
    disclosed_keys = _per_strain_cfu_disclosed_keys(pdata, clinical_strains)
    disclosed_count = min(len(disclosed_keys), total_strain_count) if total_strain_count else 0
    disclosure_score = _score_per_strain_cfu_disclosure(disclosed_count, total_strain_count)

    adequacy = _compute_cfu_adequacy(clinical_strains)
    cfu_adequacy_v3 = adequacy["v3_points"]
    cfu_adequacy_scaled = min(CAP_CFU_ADEQUACY, cfu_adequacy_v3 * 3.0)
    aggregate_proxy = _compute_aggregate_cfu_proxy(
        pdata,
        clinical_strains,
        total_strain_count=total_strain_count,
        disclosed_count=disclosed_count,
    )
    if aggregate_proxy["score"] > 0.0:
        cfu_adequacy_scaled = max(cfu_adequacy_scaled, aggregate_proxy["score"])
    # Direct per-strain mass floor: a named strain disclosed at its OWN mass (e.g.
    # BB536 25 mg) with no CFU is not "no dose disclosed". Give a conservative floor
    # (below the 8-pt aggregate-CFU proxy) so dose isn't treated as fully absent.
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
            "cfu_adequacy_contributions": adequacy["strain_contributions"],
            "aggregate_cfu_proxy": aggregate_proxy,
            "direct_strain_mass_floor": direct_strain_mass_floor,
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
        support_raw = strain.get("clinical_support_level")
        support = _norm(support_raw) or "weak"
        cfu = strain.get("cfu_per_day")

        if strain.get("is_inactivated") or strain.get("is_postbiotic"):
            contributions.append({
                "tier": tier or strain.get("adequacy_tier"),
                "support": support_raw,
                "cfu_per_day": cfu,
                "points": 0.0,
                "skipped_reason": "postbiotic_inactivated_no_cfu_credit",
            })
            continue

        if tier is None or cfu is None:
            contributions.append({
                "tier": tier or strain.get("adequacy_tier"),
                "support": support_raw,
                "cfu_per_day": cfu,
                "points": 0.0,
            })
            continue

        base = TIER_POINTS.get(tier, 0.0)
        mult = SUPPORT_LEVEL_CAPS.get(support, SUPPORT_LEVEL_CAPS["weak"])
        points = base * mult
        total += points
        contributions.append({
            "tier": tier,
            "support": support,
            "cfu_per_day": cfu,
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
        return "aggregate_cfu_modeled_proxy"
    if direct_strain_mass_floor.get("applied"):
        return "direct_strain_mass_no_cfu_floor"
    if cfu_adequacy_scaled > 0.0 and disclosed_count > 0:
        return "per_strain_cfu_disclosed"
    if cfu_adequacy_scaled > 0.0:
        return "strain_level_cfu_evidence"
    return "no_cfu_adequacy_credit"


def _ingredient_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for a in _safe_list(product.get("activeIngredients")):
        if isinstance(a, dict):
            rows.append(a)
    for a in _safe_list(product.get("ingredients")):
        if isinstance(a, dict):
            rows.append(a)
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    for key in ("ingredients_scorable", "ingredients"):
        for a in _safe_list(iqd.get(key)):
            if isinstance(a, dict):
                rows.append(a)
    return rows


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

    # Canonical strain-name keys (name/strain only — NOT short clinical_id codes,
    # which could spuriously substring-match unrelated rows).
    strain_keys = set()
    for s in strains:
        for v in (s.get("strain"), s.get("name")):
            k = _canonical_key(str(v or ""))
            if k:
                strain_keys.add(k)
    if not strain_keys:
        payload["reason"] = "no_named_strains"
        return payload

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
        rkey = _canonical_key(name)
        if not rkey:
            continue
        # The row must carry a named strain (exact, or the row name contains the
        # full strain name — never the reverse, to avoid short-token false matches).
        if any(sk == rkey or sk in rkey for sk in strain_keys):
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
    """Conservative adequacy proxy for aggregate-CFU probiotic labels.

    The proxy never grants per-strain disclosure credit. It only prevents a
    named-strain product with a real aggregate CFU from scoring dose as if no
    dose existed. Equal distribution is used as a conservative modeling proxy
    and the resulting adequacy is capped below fully disclosed CFU adequacy.
    """
    payload = {
        "applied": False,
        "score": 0.0,
        "cap": CAP_AGGREGATE_CFU_PROXY_ADEQUACY,
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
    strains = [
        strain for strain in strains
        if strain and not strain.get("is_inactivated") and not strain.get("is_postbiotic")
    ]
    if not strains:
        payload["reason"] = "no_clinical_strains_for_proxy"
        return payload

    proxy_cfu_per_strain = (total_billion * 1_000_000_000.0) / float(total_strain_count)
    proxy_tier = _tier_from_proxy_cfu(proxy_cfu_per_strain)
    if proxy_tier == "low":
        payload.update({
            "reason": "aggregate_cfu_below_proxy_floor",
            "total_billion_count": round(total_billion, 4),
            "proxy_cfu_per_strain": round(proxy_cfu_per_strain, 4),
            "proxy_tier": proxy_tier,
        })
        return payload

    total = 0.0
    contributions: List[Dict[str, Any]] = []
    for strain in strains:
        support_raw = strain.get("clinical_support_level")
        support = _norm(support_raw) or "weak"
        base = TIER_POINTS.get(proxy_tier, 0.0)
        mult = SUPPORT_LEVEL_CAPS.get(support, SUPPORT_LEVEL_CAPS["weak"])
        points = base * mult
        total += points
        contributions.append({
            "strain": strain.get("strain") or strain.get("name") or strain.get("clinical_id"),
            "proxy_tier": proxy_tier,
            "support": support,
            "points": round(points, 4),
        })

    v3_points = min(V3_CFU_ADEQUACY_CAP, total)
    score = min(CAP_AGGREGATE_CFU_PROXY_ADEQUACY, v3_points * 3.0)
    payload.update({
        "applied": score > 0.0,
        "score": round(score, 4),
        "reason": "aggregate_cfu_even_split_proxy",
        "total_billion_count": round(total_billion, 4),
        "proxy_cfu_per_strain": round(proxy_cfu_per_strain, 4),
        "proxy_tier": proxy_tier,
        "v3_points": round(v3_points, 4),
        "contributions": contributions,
    })
    return payload


def _tier_from_proxy_cfu(cfu_per_strain: float) -> str:
    if cfu_per_strain >= 10_000_000_000:
        return "excellent"
    if cfu_per_strain >= 5_000_000_000:
        return "good"
    if cfu_per_strain >= 1_000_000_000:
        return "adequate"
    return "low"


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

    for item in clinical_strains or []:
        strain = _safe_dict(item)
        if strain.get("cfu_per_day") is not None:
            key = _strain_key(strain)
            if key:
                keys.add(key)

    for blend_item in _safe_list(pdata.get("probiotic_blends")):
        blend = _safe_dict(blend_item)
        strains = [str(s).strip() for s in _safe_list(blend.get("strains")) if str(s).strip()]
        if len(strains) != 1:
            continue
        cfu_data = _safe_dict(blend.get("cfu_data"))
        if _cfu_data_has_individual_cfu(cfu_data):
            keys.add(_canonical_key(strains[0]))

    return {key for key in keys if key}


def _cfu_data_has_individual_cfu(cfu_data: Dict[str, Any]) -> bool:
    if not cfu_data.get("has_cfu"):
        return False
    # Disclosure credit is about label structure: a single-strain row with
    # `has_cfu=True` has per-strain CFU disclosed even if the numeric parser
    # did not preserve the count. Adequacy math still requires cfu_per_day.
    return True


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
    for item in clinical_strains or []:
        key = _strain_key(_safe_dict(item))
        if key:
            seen.add(key)
    return len(seen)


def _strain_key(strain: Dict[str, Any]) -> str:
    for field in ("clinical_id", "strain", "name", "standard_name"):
        value = strain.get(field)
        key = _canonical_key(str(value)) if value is not None else ""
        if key:
            return key
    return ""


def _disclosure_reason(pdata: Dict[str, Any], total_strain_count: int, disclosed_count: int) -> str | None:
    if disclosed_count > 0:
        return None
    if total_strain_count <= 0:
        return "no_strain_data"
    if pdata.get("has_cfu") or _as_float(pdata.get("total_billion_count"), 0.0) > 0:
        return "aggregate_cfu_not_per_strain"
    return "per_strain_cfu_missing"


def _total_billion_count(pdata: Dict[str, Any]) -> float:
    total_billion = _as_float(pdata.get("total_billion_count"), 0.0)
    if total_billion > 0.0:
        return total_billion
    total_cfu = _as_float(pdata.get("total_cfu"), 0.0)
    if total_cfu > 0.0:
        return total_cfu / 1_000_000_000.0
    for blend_item in _safe_list(pdata.get("probiotic_blends")):
        cfu_data = _safe_dict(_safe_dict(blend_item).get("cfu_data"))
        blend_billion = _as_float(cfu_data.get("billion_count"), 0.0)
        if blend_billion > 0.0:
            return blend_billion
        blend_cfu = _as_float(cfu_data.get("cfu_count"), 0.0)
        if blend_cfu > 0.0:
            return blend_cfu / 1_000_000_000.0
    return 0.0


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
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower()
