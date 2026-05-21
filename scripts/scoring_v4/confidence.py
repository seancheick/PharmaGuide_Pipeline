"""v4 Layer 4 — typed confidence metadata (P1.4).

Confidence is metadata, not score math. It explains how much uncertainty
surrounds a score without changing the score itself. The top-level band is
derived by worst-case across four typed sub-categories from the v4 spec:

    evidence, label_completeness, verification, identity

This module intentionally does not import the v3 scorer. It reads the v4
shadow breakdown plus the enriched product contract.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


LEVEL_ORDER = {"high": 3, "moderate": 2, "low": 1}
SCORE_UNCERTAINTY_PTS = {"high": 1, "moderate": 3, "low": 7}

PRODUCT_OR_BRANDED_EVIDENCE = {
    "product-human",
    "product-rct",
    "product",
    "branded-rct",
}
# Values in these sets must use dash form because `_norm()` below converts
# underscores to dashes. v3-enriched evidence commonly emits underscore
# study_type values (`rct_multiple`, `systematic_review_meta`); confidence
# should recognize those as human evidence after normalization.
HUMAN_STUDY_TYPES = {
    "systematic-review-meta",
    "rct-multiple",
    "rct-single",
    "clinical-strain",
}


def evaluate_confidence(
    product: Dict[str, Any],
    *,
    module_breakdown: Dict[str, Any],
    safety_gate: Dict[str, Any],
    completeness_gate: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the typed confidence object for a scoreable shadow row.

    Args:
        product: Enriched product dict.
        module_breakdown: `shadow_score_v4_breakdown["module"]`.
        safety_gate: rendered safety-gate breakdown.
        completeness_gate: rendered completeness-gate breakdown.

    Returns:
        Confidence dict. `band` is the worst-case of the four typed
        sub-category levels. `score_uncertainty_pts` is a display hint
        only; it is not applied to the numeric score.
    """
    if not isinstance(product, dict):
        product = {}
    module_breakdown = _safe_dict(module_breakdown)
    safety_gate = _safe_dict(safety_gate)
    completeness_gate = _safe_dict(completeness_gate)

    evidence = _evidence_confidence(product, module_breakdown)
    label = _label_completeness_confidence(module_breakdown)
    verification = _verification_confidence(product, module_breakdown)
    identity = _identity_confidence(product, safety_gate, completeness_gate)
    levels = [evidence[0], label[0], verification[0], identity[0]]
    band = min(levels, key=lambda level: LEVEL_ORDER[level])

    return {
        "band": band,
        "score_uncertainty_pts": SCORE_UNCERTAINTY_PTS[band],
        "evidence": _section(evidence),
        "label_completeness": _section(label),
        "verification": _section(verification),
        "identity": _section(identity),
    }


def _section(result: Tuple[str, List[str]]) -> Dict[str, Any]:
    level, drivers = result
    return {"level": level, "drivers": sorted(dict.fromkeys(drivers))}


def _evidence_confidence(product: Dict[str, Any], module: Dict[str, Any]) -> Tuple[str, List[str]]:
    evidence_dim = _dimension(module, "evidence")
    metadata = _safe_dict(evidence_dim.get("metadata"))
    score = _as_float(evidence_dim.get("score"), 0.0) or 0.0
    matched_entries = int(_as_float(metadata.get("matched_entries"), 0.0) or 0)
    clinical_matches = _clinical_matches(product)

    if matched_entries <= 0 and not clinical_matches:
        return "low", ["no_clinical_evidence_matched"]

    drivers: List[str] = []
    has_product_or_branded = any(
        _norm(match.get("evidence_level")) in PRODUCT_OR_BRANDED_EVIDENCE
        for match in clinical_matches
        if isinstance(match, dict)
    )
    has_human_study = any(
        _norm(match.get("study_type")) in HUMAN_STUDY_TYPES
        for match in clinical_matches
        if isinstance(match, dict)
    )

    if has_product_or_branded:
        level = "high"
    elif has_human_study and score >= 4.0:
        # Ingredient-human evidence is useful and common in supplements, but
        # still carries some product-specific uncertainty.
        level = "moderate"
        drivers.append("product_specific_nct_absent")
    elif has_human_study:
        level = "moderate"
        drivers.extend(["limited_human_evidence", "product_specific_nct_absent"])
    else:
        level = "low"
        drivers.append("human_clinical_evidence_absent")

    flags = [str(f) for f in _safe_list(metadata.get("flags"))]
    if "SUB_CLINICAL_DOSE_DETECTED" in flags:
        drivers.append("sub_clinical_dose_detected")
        if level == "high":
            level = "moderate"
    return level, drivers


def _label_completeness_confidence(module: Dict[str, Any]) -> Tuple[str, List[str]]:
    dimensions = _safe_dict(module.get("dimensions"))
    dose = _safe_dict(dimensions.get("dose"))
    dose_meta = _safe_dict(dose.get("metadata"))
    transparency = _safe_dict(dimensions.get("transparency"))
    penalties = _safe_dict(transparency.get("penalties"))
    trans_meta = _safe_dict(transparency.get("metadata"))
    drivers: List[str] = []
    level = "high"

    if dose_meta.get("window_proxy_status") == "not_evaluable_by_rda_proxy":
        level = _min_level(level, "moderate")
        drivers.append("dose_window_not_evaluable_by_rda_proxy")

    # Probiotic-specific (P2.6): aggregate CFU disclosed but not per-strain.
    # `window_proxy_reason` comes from probiotic_dose.score_dose metadata.
    # Values: "aggregate_cfu_not_per_strain" (has aggregate but no per-strain
    # CFU — the common case for shipped probiotics), "no_strain_data" (no
    # strain info at all), "per_strain_cfu_missing" (strains named but no
    # CFU values). All three are label-completeness gaps surfacing the
    # spec's "Strain-level CFU not disclosed" caveat per §5 line 255.
    dose_reason = dose_meta.get("window_proxy_reason")
    if dose_reason in {"aggregate_cfu_not_per_strain",
                       "no_strain_data",
                       "per_strain_cfu_missing"}:
        level = _min_level(level, "moderate")
        drivers.append("per_strain_cfu_not_disclosed")

    b5 = abs(_as_float(penalties.get("B5_proprietary_blend_opacity"), 0.0) or 0.0)
    if b5 >= 5.0:
        level = "low"
        drivers.append("high_proprietary_blend_opacity")
    elif b5 > 0.0:
        level = _min_level(level, "moderate")
        drivers.append("partial_proprietary_blend_opacity")

    flags = set(str(f) for f in _safe_list(trans_meta.get("flags")))
    if "LABEL_CONTRADICTION_DETECTED" in flags:
        level = _min_level(level, "moderate")
        drivers.append("label_claim_contradiction")
    if "DISEASE_CLAIM_PENALTY" in flags:
        level = _min_level(level, "moderate")
        drivers.append("disease_claim_penalty_present")
    return level, drivers


def _verification_confidence(product: Dict[str, Any], module: Dict[str, Any]) -> Tuple[str, List[str]]:
    trust = _dimension(module, "trust")
    metadata = _safe_dict(trust.get("metadata"))
    scope_counts = _safe_dict(metadata.get("verified_scope_counts"))
    if _as_float(scope_counts.get("sku"), 0.0):
        return "high", ["cert_sku_verified"]
    if _as_float(scope_counts.get("product_line"), 0.0):
        return "high", ["cert_product_line_verified"]
    if _as_float(scope_counts.get("label_asserted_product"), 0.0):
        return "moderate", ["cert_label_asserted_product"]

    cert_entries = _verified_cert_entries(product)
    drivers: List[str] = []
    level = "moderate"
    if not cert_entries:
        return "moderate", ["no_verified_third_party_certification"]

    for entry in cert_entries:
        if not isinstance(entry, dict):
            continue
        scope = _norm(entry.get("scope")).replace("-", "_")
        if entry.get("scoring_blocked_reason"):
            drivers.append("cert_registry_stale_or_blocked")
            level = "low"
        elif scope == "needs_review":
            drivers.append("cert_match_needs_review")
            level = "low"
        elif scope == "claimed_only":
            drivers.append("cert_claimed_only_no_registry_match")
            level = "low"
        elif scope == "brand_only":
            drivers.append("brand_cert_not_sku_verified")
        elif scope:
            drivers.append(f"cert_scope_{scope}")

    signals = product.get("manufacturer_cert_signals")
    if isinstance(signals, list) and signals:
        drivers.append("manufacturer_signal_present_no_sku_match")

    return level, drivers or ["third_party_verification_unresolved"]


def _identity_confidence(
    product: Dict[str, Any],
    safety_gate: Dict[str, Any],
    completeness_gate: Dict[str, Any],
) -> Tuple[str, List[str]]:
    drivers: List[str] = []
    level = "high"

    if safety_gate.get("needs_review") is True:
        return "low", ["safety_identity_match_needs_review"]

    mapped_coverage = _as_float(completeness_gate.get("mapped_coverage"), None)
    if mapped_coverage is not None and mapped_coverage < 0.95:
        level = _min_level(level, "moderate")
        drivers.append("mapped_coverage_below_95_percent")

    for confidence in _ingredient_identity_confidences(product):
        if confidence < 0.80:
            return "low", ["ingredient_identity_confidence_below_80_percent"]
        if confidence < 0.95:
            level = _min_level(level, "moderate")
            drivers.append("ingredient_identity_confidence_below_95_percent")

    if _norm(product.get("form_factor_source")) == "inferred" or _norm(product.get("form_source")) == "inferred":
        level = _min_level(level, "moderate")
        drivers.append("form_factor_inferred")

    for driver in _supp_type_driver(product):
        level = _min_level(level, "moderate")
        drivers.append(driver)

    return level, drivers


_TAXONOMY_CONFIDENCE_THRESHOLD = 0.70
_LEGACY_SUPP_CONFIDENCE_THRESHOLD = 0.80


def _supp_type_driver(product: Any) -> List[str]:
    """Return the product-class confidence driver, if one should be emitted.

    Taxonomy confidence is the canonical signal for current enriched batches.
    Legacy `supplement_type.confidence` is kept only as a fallback for old
    blobs that do not have taxonomy yet.
    """
    if not isinstance(product, dict):
        return []

    taxonomy = product.get("supplement_taxonomy")
    if isinstance(taxonomy, dict):
        tax_conf = _as_float(taxonomy.get("classification_confidence"), None)
        if tax_conf is not None:
            if tax_conf < _TAXONOMY_CONFIDENCE_THRESHOLD:
                return ["taxonomy_classification_low_confidence"]
            return []

    supp = product.get("supplement_type")
    if isinstance(supp, dict):
        supp_conf = _as_float(supp.get("confidence"), None)
        if supp_conf is not None and supp_conf < _LEGACY_SUPP_CONFIDENCE_THRESHOLD:
            return ["supplement_type_low_confidence"]
    return []


def _clinical_matches(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = _safe_dict(product.get("evidence_data"))
    matches = _safe_list(evidence.get("clinical_matches"))
    if not matches:
        matches = _safe_list(_safe_dict(product.get("clinical_evidence")).get("clinical_matches"))
    return [m for m in matches if isinstance(m, dict)]


def _verified_cert_entries(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = product.get("verified_cert_programs")
    if entries is None:
        entries = _safe_dict(product.get("certification_data")).get("verified_cert_programs")
    return [e for e in _safe_list(entries) if isinstance(e, dict)]


def _ingredient_identity_confidences(product: Dict[str, Any]) -> Iterable[float]:
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    rows = (
        _safe_list(iqd.get("ingredients_scorable"))
        or _safe_list(iqd.get("ingredients"))
        or _safe_list(product.get("activeIngredients"))
        or _safe_list(product.get("active_ingredients"))
    )
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("identity_confidence", "match_confidence", "canonical_confidence"):
            value = _as_float(row.get(key), None)
            if value is not None:
                yield value
                break


def _dimension(module: Dict[str, Any], name: str) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(module.get("dimensions")).get(name))


def _min_level(current: str, candidate: str) -> str:
    return current if LEVEL_ORDER[current] <= LEVEL_ORDER[candidate] else candidate


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("_", "-")


def _as_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
