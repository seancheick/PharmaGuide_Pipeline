"""v4 generic-module Transparency dimension (P1.3.5).

Transparency (10) is the user-facing home for disclosure quality:

    clear disclosure base             6
    complete active identity+dose     +3
    B3 claim compliance              +4
    B2 false allergen-free claim     -2
    B5 proprietary blend opacity     -10 (class-aware)
    B6 marketing / disease claims    -5

Final: clamp(0, 10, base + B3 - penalty magnitudes).

This module re-implements the mature v3 B2/B3/B5/B6 logic without
importing `score_supplements.py`, preserving the v4 shadow architecture
lock while keeping arithmetic parity with production v3 inputs.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    get_active_ingredients,
    has_usable_individual_dose,
)


PHASE_MARKER = "P1.3.5_transparency"

DIMENSION_CAP = 10.0
CLEAR_DISCLOSURE_BASE = 6.0
COMPLETE_ACTIVE_DISCLOSURE_BONUS = 3.0

B2_CAP = 2.0
B2_SEVERITY_POINTS = {
    "high": 2.0,
    "moderate": 1.5,
    "low": 1.0,
}

B3_CAP = 4.0
B3_ALLERGEN_FREE = 2.0
B3_GLUTEN_FREE = 1.0
B3_VEGAN_OR_VEGETARIAN = 1.0

B5_BASE = {"full": 0.0, "partial": 1.0, "none": 2.0}
B5_PROP_COEF = {"full": 0.0, "partial": 3.0, "none": 5.0}
B5_CAP = 10.0
B5_COUNT_DENOM_MIN = 8
B5_CLASS_MULTIPLIERS = {
    "probiotic": 0.4,
    "multi_or_prenatal": 1.3,
    "sports_active": 1.5,
    "generic": 1.0,
}
B5_PRENATAL_KEYWORDS = re.compile(
    r"\b(prenatal|pregnancy|pre-natal|expecting|maternal|gestation)\b",
    re.IGNORECASE,
)
B5_SPORTS_KEYWORDS = re.compile(
    r"\b(pre[-\s]?workout|post[-\s]?workout|intra[-\s]?workout|"
    r"bcaa|eaa|creatine|beta[-\s]?alanine|nitric[-\s]?oxide|"
    r"energy\s+matrix|pump|stim\s+stack|thermogenic|fat\s+burner|"
    r"whey|casein|"
    r"protein\s+(?:isolate|blend|complex|matrix|powder|concentrate|hydrolysate))\b",
    re.IGNORECASE,
)
B5_GENERIC_OVERRIDE_KEYWORDS = re.compile(
    r"\b(dha|epa|omega[-\s]?3|fish\s+oil|krill|cod\s+liver|"
    r"enzyme|enzymes|glucosamine|chondroitin|msm|collagen)\b",
    re.IGNORECASE,
)
B5_GENERIC_OVERRIDE_PRIMARY_CATEGORIES = {
    "omega-3",
    "omega 3",
    "protein",
    "collagen",
    "enzyme",
    "enzymes",
}

B6_DISEASE_CLAIM_PENALTY = 5.0


def score_transparency(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute generic Transparency."""
    if not isinstance(product, dict):
        product = {}

    flags: List[str] = []
    b2, b2_meta = _score_b2_false_allergen_claim_penalty(product)
    allergen_valid, gluten_valid, vegan_valid, claim_flags = _derive_claim_validations(product, b2)
    flags.extend(claim_flags)
    b3 = _score_b3_claim_compliance(
        allergen_free=allergen_valid,
        gluten_free=gluten_valid,
        vegan_or_vegetarian=vegan_valid,
    )
    b5, b5_evidence = _score_b5_proprietary_blend_penalty(product, flags)
    b6 = _score_b6_disease_claim_penalty(product, flags)
    complete_active_bonus, complete_active_meta = _score_complete_active_disclosure_bonus(
        product,
        b5_penalty=b5,
        b6_penalty=b6,
    )

    components = {
        "clear_disclosure_base": CLEAR_DISCLOSURE_BASE,
        "complete_active_identity_dose_disclosure": round(complete_active_bonus, 4),
        "B3_claim_compliance": round(b3, 4),
        # The v3 feature gate for hypoallergenic bonus is disabled in the
        # shipped config. Keep the line explicit so v4 display has a stable
        # slot if/when the gate is intentionally enabled later.
        "hypoallergenic_bonus": 0.0,
    }
    penalties = {
        "B2_false_allergen_free_claim": _negative_or_zero(b2),
        "B5_proprietary_blend_opacity": _negative_or_zero(b5),
        "B6_marketing_claims": _negative_or_zero(b6),
    }
    raw_total = (
        sum(float(v) for v in components.values())
        - sum(abs(float(v)) for v in penalties.values())
    )
    score = _clamp(0.0, DIMENSION_CAP, raw_total)

    metadata = {
        "phase": PHASE_MARKER,
        "raw_transparency": round(raw_total, 4),
        "cap_applied": raw_total > DIMENSION_CAP,
        "floor_applied": raw_total < 0.0,
        "claim_validations": {
            "allergen_free": bool(allergen_valid),
            "gluten_free": bool(gluten_valid),
            "vegan_or_vegetarian": bool(vegan_valid),
        },
        "flags": sorted(set(flags)),
        "B2_raw_before_cap": round(b2_meta["raw_before_cap"], 4),
        "B2_seen_allergens": b2_meta["seen_allergens"],
        "claimed_allergen_groups": b2_meta.get("claimed_allergen_groups", []),
        "present_allergen_groups": b2_meta.get("present_allergen_groups", []),
        "conflict_allergen_groups": b2_meta.get("conflict_allergen_groups", []),
        "matched_false_claim_groups": b2_meta.get("matched_false_claim_groups", []),
        "B5_blend_evidence": b5_evidence,
        "B5_blend_count": len(b5_evidence),
        "B5_raw_before_cap": round(sum(e["computed_blend_penalty_magnitude"] for e in b5_evidence), 4),
        "complete_active_disclosure": complete_active_meta,
    }

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _score_b2_allergen_penalty(product: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    return _score_b2_false_allergen_claim_penalty(product)


def _score_b2_false_allergen_claim_penalty(product: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    allergens = _safe_list(
        _safe_dict(_safe_dict(product.get("contaminant_data")).get("allergens")).get(
            "allergens", product.get("allergen_hits", [])
        )
    )
    seen: Dict[str, float] = {}
    for item in allergens:
        if not isinstance(item, dict):
            continue
        severity = B2_SEVERITY_POINTS.get(_norm_text(item.get("severity_level")), 0.0)
        key = _norm_text(
            item.get("allergen_id")
            or item.get("allergen_type")
            or item.get("allergen_name")
            or item.get("allergen")
            or item.get("name")
        )
        if key:
            seen[key] = max(seen.get(key, 0.0), severity)

    compliance = _safe_dict(product.get("compliance_data"))
    conflicts = [_norm_text(x) for x in _safe_list(compliance.get("conflicts"))]
    claim_groups = _claimed_allergen_groups(compliance)
    present_groups = _present_allergen_groups(seen)
    conflict_groups = _conflict_allergen_groups(conflicts)

    matched_groups = sorted(
        (present_groups | conflict_groups)
        if "allergen" in claim_groups
        else claim_groups & (present_groups | conflict_groups)
    )
    conflict_only = bool(conflicts and claim_groups and conflict_groups and not matched_groups)
    if conflict_only:
        matched_groups = sorted(conflict_groups)

    raw = 0.0
    if matched_groups:
        raw = max((seen.get(group, 0.0) for group in matched_groups), default=0.0)
        if raw == 0.0:
            raw = B2_CAP
    elif claim_groups and bool(compliance.get("has_may_contain_warning", False)):
        raw = B2_CAP

    return _clamp(0.0, B2_CAP, raw), {
        "raw_before_cap": raw,
        "seen_allergens": dict(sorted(seen.items())),
        "claimed_allergen_groups": sorted(claim_groups),
        "present_allergen_groups": sorted(present_groups),
        "conflict_allergen_groups": sorted(conflict_groups),
        "matched_false_claim_groups": matched_groups,
    }


def _derive_claim_validations(
    product: Dict[str, Any],
    b2_penalty: float,
) -> Tuple[bool, bool, bool, List[str]]:
    flags: List[str] = []
    explicit_allergen = product.get("claim_allergen_free_validated")
    explicit_gluten = product.get("claim_gluten_free_validated")
    explicit_vegan = product.get("claim_vegan_validated")
    if explicit_allergen is not None and explicit_gluten is not None and explicit_vegan is not None:
        return bool(explicit_allergen), bool(explicit_gluten), bool(explicit_vegan), flags

    compliance = _safe_dict(product.get("compliance_data"))
    conflicts = [_norm_text(x) for x in _safe_list(compliance.get("conflicts"))]
    has_may_contain = bool(compliance.get("has_may_contain_warning", False))

    if explicit_allergen is None:
        allergen_claims = _safe_list(compliance.get("allergen_free_claims"))
        contradiction = has_may_contain or any(
            any(term in conflict for term in ("allergen", "dairy", "soy", "egg", "gluten", "wheat", "shellfish", "nut"))
            for conflict in conflicts
        )
        allergen_valid = bool(allergen_claims) and not contradiction and b2_penalty == 0.0
    else:
        allergen_valid = bool(explicit_allergen)

    if explicit_gluten is None:
        gluten_claim = bool(compliance.get("gluten_free", False))
        contradiction = has_may_contain or any(
            ("gluten" in conflict) or ("wheat" in conflict) for conflict in conflicts
        )
        gluten_valid = gluten_claim and not contradiction
    else:
        gluten_valid = bool(explicit_gluten)

    if explicit_vegan is None:
        vegan_claim = bool(compliance.get("vegan", False) or compliance.get("vegetarian", False))
        contradiction = any(
            any(term in conflict for term in ("gelatin", "bovine", "porcine", "vegan", "vegetarian"))
            for conflict in conflicts
        )
        vegan_valid = vegan_claim and not contradiction
    else:
        vegan_valid = bool(explicit_vegan)

    has_any_claim = bool(
        compliance.get("allergen_free_claims")
        or compliance.get("gluten_free")
        or compliance.get("vegan")
        or compliance.get("vegetarian")
    )
    if has_any_claim and conflicts:
        flags.append("LABEL_CONTRADICTION_DETECTED")

    return allergen_valid, gluten_valid, vegan_valid, flags


def _claimed_allergen_groups(compliance: Dict[str, Any]) -> set[str]:
    groups: set[str] = set()
    for claim in _safe_list(compliance.get("allergen_free_claims")):
        text_parts: List[str] = []
        if isinstance(claim, dict):
            text_parts.extend(
                str(claim.get(key) or "")
                for key in ("allergen", "allergen_type", "claim", "claim_type", "id", "dedupe_key", "display_name")
            )
        else:
            text_parts.append(str(claim))
        for text in text_parts:
            groups.update(_allergen_groups_from_text(text))
    if bool(compliance.get("gluten_free", False)):
        groups.add("gluten")
    return groups


def _present_allergen_groups(seen: Dict[str, float]) -> set[str]:
    groups: set[str] = set()
    for text in seen:
        groups.update(_allergen_groups_from_text(text))
    return groups


def _conflict_allergen_groups(conflicts: List[str]) -> set[str]:
    groups: set[str] = set()
    for text in conflicts:
        groups.update(_allergen_groups_from_text(text))
    return groups


def _allergen_groups_from_text(text: str) -> set[str]:
    norm = _norm_text(text)
    if not norm:
        return set()

    groups: set[str] = set()
    if "allergen" in norm and "free" in norm:
        groups.add("allergen")
    if any(term in norm for term in ("gluten", "wheat", "barley", "rye", "kamut", "spelt")):
        groups.add("gluten")
    if any(term in norm for term in ("dairy", "milk", "casein", "whey", "lactose")):
        groups.add("dairy")
    if "soy" in norm:
        groups.add("soy")
    if "egg" in norm:
        groups.add("egg")
    if any(term in norm for term in ("shellfish", "crustacean", "shrimp", "crab", "lobster")):
        groups.add("shellfish")
    if any(term in norm for term in ("peanut", "groundnut")):
        groups.add("peanut")
    if any(term in norm for term in ("tree nut", "treenut", "almond", "cashew", "walnut", "pecan", "hazelnut", "pistachio")):
        groups.add("tree_nut")
    elif "nut" in norm:
        groups.add("tree_nut")
    if "yeast" in norm:
        groups.add("yeast")
    if "sesame" in norm:
        groups.add("sesame")
    return groups


def _score_b3_claim_compliance(
    *,
    allergen_free: bool,
    gluten_free: bool,
    vegan_or_vegetarian: bool,
) -> float:
    raw = (
        (B3_ALLERGEN_FREE if allergen_free else 0.0)
        + (B3_GLUTEN_FREE if gluten_free else 0.0)
        + (B3_VEGAN_OR_VEGETARIAN if vegan_or_vegetarian else 0.0)
    )
    return _clamp(0.0, B3_CAP, raw)


def _score_complete_active_disclosure_bonus(
    product: Dict[str, Any],
    *,
    b5_penalty: float,
    b6_penalty: float,
) -> Tuple[float, Dict[str, Any]]:
    """Reward complete active identity + dose disclosure.

    B3 rewards validated clean-label claims. A product can be fully
    transparent about what matters clinically (active identity and dose)
    without making any gluten-free / vegan / allergen-free claim, so keep
    that disclosure credit in its own lane. The gate is intentionally
    conservative: every declared active must be represented by an
    individually dose-bearing row, and proprietary/parent-total rows do
    not qualify.
    """
    rows = [row for row in get_active_ingredients(product) if isinstance(row, dict)]
    declared_count = _declared_active_count(product, rows)

    blockers: List[str] = []
    if not rows:
        blockers.append("no_active_rows")
    if declared_count <= 0:
        blockers.append("no_declared_active_count")
    if declared_count > len(rows):
        blockers.append("declared_count_exceeds_rows")
    if b5_penalty > 0.0:
        blockers.append("proprietary_blend_opacity")
    if b6_penalty > 0.0:
        blockers.append("disease_or_marketing_claim")

    complete_rows = 0
    incomplete_rows: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        row_blockers: List[str] = []
        if row.get("is_proprietary_blend"):
            row_blockers.append("proprietary_blend_row")
        if row.get("is_parent_total"):
            row_blockers.append("parent_total_row")
        if not _has_active_identity(row):
            row_blockers.append("missing_identity")
        if not _has_usable_disclosure_dose(row):
            row_blockers.append("missing_usable_dose")
        if row_blockers:
            incomplete_rows.append(
                {
                    "index": idx,
                    "name": row.get("name") or row.get("standard_name") or "",
                    "blockers": row_blockers,
                }
            )
        else:
            complete_rows += 1

    if complete_rows < declared_count:
        blockers.append("incomplete_active_rows")

    qualifies = not blockers
    return (COMPLETE_ACTIVE_DISCLOSURE_BONUS if qualifies else 0.0), {
        "qualifies": bool(qualifies),
        "bonus": COMPLETE_ACTIVE_DISCLOSURE_BONUS if qualifies else 0.0,
        "declared_active_count": declared_count,
        "active_row_count": len(rows),
        "complete_row_count": complete_rows,
        "blockers": sorted(set(blockers)),
        "incomplete_rows": incomplete_rows[:10],
    }


def _declared_active_count(product: Dict[str, Any], rows: List[Dict[str, Any]]) -> int:
    proprietary = _safe_dict(product.get("proprietary_data"))
    quality = _safe_dict(product.get("ingredient_quality_data"))
    for value in (
        proprietary.get("total_active_ingredients"),
        quality.get("total_active"),
        quality.get("total_active_ingredients"),
    ):
        parsed = int(_as_float(value, 0) or 0)
        if parsed > 0:
            return parsed
    return len(rows)


def _has_active_identity(row: Dict[str, Any]) -> bool:
    return any(row.get(field) for field in ("canonical_id", "standard_name", "name"))


def _has_usable_disclosure_dose(row: Dict[str, Any]) -> bool:
    if has_usable_individual_dose(row):
        return True
    for key in ("amount", "dose", "quantity_mg", "amount_mg"):
        value = _as_float(row.get(key), None)
        if value is not None and value > 0:
            return True
    return False


def _score_b6_disease_claim_penalty(product: Dict[str, Any], flags: List[str]) -> float:
    has_claims = bool(product.get("has_disease_claims", False))
    if not has_claims:
        has_claims = bool(_safe_dict(product.get("product_signals")).get("has_disease_claims", False))
    if not has_claims:
        has_claims = bool(
            _safe_dict(_safe_dict(product.get("evidence_data")).get("unsubstantiated_claims")).get(
                "found", False
            )
        )
    if has_claims:
        flags.append("DISEASE_CLAIM_DETECTED")
        return B6_DISEASE_CLAIM_PENALTY
    return 0.0


def _score_b5_proprietary_blend_penalty(
    product: Dict[str, Any],
    flags: List[str],
) -> Tuple[float, List[Dict[str, Any]]]:
    blends = _get_disclosure_blends(product)
    if not blends:
        return 0.0, []

    flags.append("PROPRIETARY_BLEND_PRESENT")

    scoreable_blends = [
        blend
        for blend in _sort_blends_for_b5_dedupe([b for b in blends if isinstance(b, dict)])
        if _is_b5_scoreable_blend(blend)
    ]
    detector_placeholder_sources = {
        _norm_text(_source_path_for_blend(blend))
        for blend in scoreable_blends
        if _is_detector_placeholder_blend(blend)
    }
    family_source_keys: Dict[Tuple[str, ...], set[Tuple[str, ...]]] = {}
    for blend in scoreable_blends:
        source_path = _norm_text(_source_path_for_blend(blend))
        name_total_key = _blend_name_total_key(blend)
        if source_path in detector_placeholder_sources and name_total_key is not None:
            family_source_keys.setdefault(name_total_key, set()).add(("source", source_path))

    deduped: List[Dict[str, Any]] = []
    seen_keys: set[Tuple[str, ...]] = set()
    for blend in scoreable_blends:
        key_set = _blend_dedupe_keys(blend, detector_placeholder_sources, family_source_keys)
        if key_set & seen_keys:
            continue
        seen_keys.update(key_set)
        deduped.append(blend)
    if not deduped:
        return 0.0, []

    proprietary = _safe_dict(product.get("proprietary_data"))
    total_active_mg = _as_float(proprietary.get("total_active_mg"), None)
    if total_active_mg is None:
        total_active_mg = _sum_total_active_mg(product)
    total_active_count = int(
        _as_float(proprietary.get("total_active_ingredients"), 0)
        or _as_float(_safe_dict(product.get("ingredient_quality_data")).get("total_active"), 0)
        or len(get_active_ingredients(product))
        or 0
    )

    blend_class = _b5_class_for_product(product)
    class_multiplier = float(B5_CLASS_MULTIPLIERS.get(blend_class, 1.0))
    evidence_rows: List[Dict[str, Any]] = []
    penalty_sum = 0.0

    for blend in _sort_blends_for_b5_dedupe(deduped):
        level = _effective_blend_disclosure_level(blend)
        base = B5_BASE.get(level, B5_BASE["none"])
        prop_coef = B5_PROP_COEF.get(level, B5_PROP_COEF["none"])
        source_path = _source_path_for_blend(blend)
        source_field = source_path.split("[", 1)[0] if source_path else ""

        children_with_amounts, children_without_amounts = _blend_child_payload(blend)
        blend_total_raw = (
            blend.get("blend_total_mg")
            if blend.get("blend_total_mg") is not None
            else blend.get("total_weight")
        )
        if blend_total_raw is not None and (
            not isinstance(blend_total_raw, (int, float)) or blend_total_raw <= 0
        ):
            blend_total_raw = None
        blend_total_unit = "mg" if blend.get("blend_total_mg") is not None else blend.get("unit")
        blend_total_mg, blend_unit_failed = _quantity_to_mg(blend_total_raw, blend_total_unit)

        disclosed_child_mg_sum = 0.0
        child_unit_failed = False
        for child in children_with_amounts:
            child_mg, child_failed = _quantity_to_mg(child.get("amount"), child.get("unit"))
            if child_failed:
                child_unit_failed = True
            if child_mg is not None and child_mg > 0:
                disclosed_child_mg_sum += child_mg

        hidden_mass_mg = None
        impact_floor_applied = False
        if blend_total_mg is not None and total_active_mg and total_active_mg > 0:
            disclosed_clamped = min(disclosed_child_mg_sum, blend_total_mg)
            hidden_mass_mg = max(blend_total_mg - disclosed_clamped, 0.0)
            impact = _clamp(0.0, 1.0, hidden_mass_mg / total_active_mg)
            if hidden_mass_mg > 0 and impact < 0.1:
                impact = 0.1
                impact_floor_applied = True
            impact_source = "mg_share"
            disclosed_child_mg_sum = disclosed_clamped
        else:
            hidden_count = int(_as_float(blend.get("hidden_count"), 0) or 0)
            if hidden_count <= 0:
                hidden_count = len(children_without_amounts)
            if hidden_count <= 0:
                hidden_count = int(_as_float(blend.get("nested_count"), 0) or 0)
            denominator = max(total_active_count, B5_COUNT_DENOM_MIN)
            impact = _clamp(0.0, 1.0, hidden_count / max(denominator, 1))
            impact_source = "count_share"

        raw_blend_penalty = 0.0 if level == "full" else base + (prop_coef * impact)
        blend_penalty = raw_blend_penalty * class_multiplier
        penalty_sum += blend_penalty

        evidence_rows.append(
            {
                "blend_name": blend.get("name") or "",
                "disclosure_tier": level,
                "blend_class": blend_class,
                "class_multiplier_applied": round(class_multiplier, 4),
                "blend_total_mg": None if blend_total_mg is None else round(blend_total_mg, 4),
                "disclosed_child_mg_sum": round(disclosed_child_mg_sum, 4),
                "hidden_mass_mg": None if hidden_mass_mg is None else round(hidden_mass_mg, 4),
                "impact_ratio": round(impact, 6),
                "impact_source": impact_source,
                "impact_floor_applied": bool(impact_floor_applied),
                "presence_penalty": round(base, 4),
                "proportional_coef": round(prop_coef, 4),
                "base_penalty_formula": (
                    "full: 0"
                    if level == "full"
                    else ("partial: -(1 + 3*impact)" if level == "partial" else "none: -(2 + 5*impact)")
                ),
                "computed_blend_penalty": round(-blend_penalty, 4),
                "computed_blend_penalty_magnitude": round(blend_penalty, 4),
                "dedupe_fingerprint": _fingerprint_to_string(_blend_dedupe_fingerprint(blend)),
                "source_field": source_field,
                "source_path": source_path,
                "unit_conversion_failed": bool(blend_unit_failed or child_unit_failed),
                "children_with_amount_count": len(children_with_amounts),
                "children_without_amount_count": len(children_without_amounts),
            }
        )

    return _clamp(0.0, B5_CAP, penalty_sum), evidence_rows


def _get_disclosure_blends(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    blends = _safe_list(product.get("proprietary_blends"))
    if blends:
        return _sort_blends_for_b5_dedupe([b for b in blends if isinstance(b, dict)])
    return _sort_blends_for_b5_dedupe(
        [b for b in _safe_list(_safe_dict(product.get("proprietary_data")).get("blends", [])) if isinstance(b, dict)]
    )


def _b5_class_for_product(product: Dict[str, Any]) -> str:
    """Return the B5 opacity class using the shared v4 router.

    This is not a separate product classifier. It delegates module/class
    selection to `scoring_v4.router.class_for_product`, then applies only
    B5-specific overlays: sports products get their own opacity multiplier,
    and omega products roll into the generic opacity tier because B5 has no
    dedicated omega multiplier.
    """
    from scoring_v4.router import class_for_product

    name_text = " ".join(
        str(product.get(key) or "")
        for key in ("product_name", "fullName", "brand_name", "bundleName")
    )

    scoring_class = class_for_product(product)
    if scoring_class == "probiotic":
        return "probiotic"

    if B5_SPORTS_KEYWORDS.search(name_text):
        return "sports_active"

    if scoring_class == "multi_or_prenatal":
        return "multi_or_prenatal"
    return "generic"


def _is_b5_scoreable_blend(blend: Dict[str, Any]) -> bool:
    source_path = _norm_text(blend.get("source_path") or blend.get("source_field") or "")
    source_prefix = source_path.split("[", 1)[0]
    sources = {_norm_text(item) for item in _safe_list(blend.get("sources")) if _norm_text(item)}
    detector_only = bool(sources) and sources == {"detector"}

    children_with, children_without = _blend_child_payload(blend)
    has_child_evidence = bool(children_with or children_without)
    hidden_count = int(_as_float(blend.get("hidden_count"), 0) or 0)
    nested_count = int(_as_float(blend.get("nested_count"), 0) or 0)

    blend_total_raw = (
        blend.get("blend_total_mg")
        if blend.get("blend_total_mg") is not None
        else blend.get("total_weight")
    )
    if blend_total_raw is not None and (
        not isinstance(blend_total_raw, (int, float)) or blend_total_raw <= 0
    ):
        blend_total_raw = None
    blend_total_unit = "mg" if blend.get("blend_total_mg") is not None else blend.get("unit")
    blend_total_mg, _ = _quantity_to_mg(blend_total_raw, blend_total_unit)
    has_total_amount = blend_total_mg is not None and blend_total_mg > 0

    if source_prefix == "activeingredients":
        return (
            _looks_like_blend_container_name(blend.get("name"))
            or has_total_amount
            or has_child_evidence
            or hidden_count > 0
            or nested_count > 0
        )
    if detector_only and source_prefix in {"statements", "inactiveingredients"}:
        return has_total_amount or has_child_evidence
    return True


def _blend_child_payload(blend: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    children_with_amounts: List[Dict[str, Any]] = []
    children_without_amounts: List[str] = []

    for child in _safe_list(blend.get("child_ingredients")):
        if not isinstance(child, dict):
            continue
        name = child.get("name") or child.get("ingredient") or ""
        amount = _as_float(child.get("amount"), None)
        if amount is None or amount <= 0:
            if name:
                children_without_amounts.append(str(name))
            continue
        children_with_amounts.append(
            {
                "name": name,
                "amount": amount,
                "unit": child.get("unit") or child.get("unit_normalized") or "mg",
            }
        )

    evidence = _safe_dict(blend.get("evidence"))
    for child in _safe_list(evidence.get("ingredients_with_amounts")):
        if not isinstance(child, dict):
            continue
        name = child.get("name") or child.get("ingredient") or ""
        amount = _as_float(child.get("amount"), None)
        if amount is None or amount <= 0:
            continue
        children_with_amounts.append(
            {
                "name": name,
                "amount": amount,
                "unit": child.get("unit") or child.get("unit_normalized") or "mg",
            }
        )
    for child in _safe_list(evidence.get("ingredients_without_amounts")):
        name = child.get("name") or child.get("ingredient") or "" if isinstance(child, dict) else str(child or "")
        if name:
            children_without_amounts.append(name)

    seen_with = set()
    deduped_with: List[Dict[str, Any]] = []
    for child in children_with_amounts:
        key = (_canon_key(child.get("name")), _as_float(child.get("amount"), 0.0), _norm_text(child.get("unit")))
        if key in seen_with:
            continue
        seen_with.add(key)
        deduped_with.append(child)

    seen_without = set()
    deduped_without: List[str] = []
    for name in children_without_amounts:
        key = _canon_key(name)
        if not key or key in seen_without:
            continue
        seen_without.add(key)
        deduped_without.append(name)

    return deduped_with, deduped_without


def _sort_blends_for_b5_dedupe(blends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer the most informative representation when the cleaner emits both
    detector placeholders and detailed parent/child records for one blend."""

    return sorted(blends, key=_b5_blend_preference_key)


def _b5_blend_preference_key(blend: Dict[str, Any]) -> Tuple[int, int, int, int, str]:
    detector_only = _is_detector_placeholder_blend(blend)
    children_with, children_without = _blend_child_payload(blend)
    has_child_evidence = bool(children_with or children_without)
    blend_total_mg, _ = _blend_total_mg(blend)
    has_total = blend_total_mg is not None and blend_total_mg > 0
    disclosure_rank = {"full": 0, "partial": 1, "none": 2}.get(
        _effective_blend_disclosure_level(blend),
        2,
    )
    return (
        1 if detector_only else 0,
        0 if has_child_evidence else 1,
        0 if has_total else 1,
        disclosure_rank,
        _source_path_for_blend(blend),
    )


def _is_detector_placeholder_blend(blend: Dict[str, Any]) -> bool:
    sources = {_norm_text(item) for item in _safe_list(blend.get("sources")) if _norm_text(item)}
    return bool(sources) and sources == {"detector"}


def _effective_blend_disclosure_level(blend: Dict[str, Any]) -> str:
    level = _norm_text(blend.get("disclosure_level")) or "none"
    if level == "none":
        blend_total_mg, _ = _blend_total_mg(blend)
        _, children_without = _blend_child_payload(blend)
        if blend_total_mg is not None and blend_total_mg > 0 and children_without:
            return "partial"
    return level


def _blend_dedupe_keys(
    blend: Dict[str, Any],
    detector_placeholder_sources: set[str] | None = None,
    family_source_keys: Dict[Tuple[str, ...], set[Tuple[str, ...]]] | None = None,
) -> set[Tuple[str, ...]]:
    keys: set[Tuple[str, ...]] = set()
    source_path = _norm_text(_source_path_for_blend(blend))
    if source_path and (
        _is_detector_placeholder_blend(blend)
        or source_path in (detector_placeholder_sources or set())
    ):
        keys.add(("source", source_path))

    name_total_key = _blend_name_total_key(blend)
    if name_total_key is not None:
        keys.add(name_total_key)
        keys.update((family_source_keys or {}).get(name_total_key, set()))

    if not keys:
        keys.add(("fingerprint", _fingerprint_to_string(_blend_dedupe_fingerprint(blend))))
    return keys


def _blend_name_total_key(blend: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
    name_key = _canon_key(blend.get("name"))
    blend_total_mg, _ = _blend_total_mg(blend)
    if not name_key or blend_total_mg is None:
        return None
    return ("name_total", name_key, f"{round(blend_total_mg, 3):.3f}")


def _blend_total_mg(blend: Dict[str, Any]) -> Tuple[Optional[float], bool]:
    amount_value = (
        blend.get("blend_total_mg")
        if blend.get("blend_total_mg") is not None
        else blend.get("total_weight")
    )
    amount_unit = "mg" if blend.get("blend_total_mg") is not None else blend.get("unit")
    return _quantity_to_mg(amount_value, amount_unit)


def _blend_dedupe_fingerprint(blend: Dict[str, Any]) -> Tuple[str, Tuple[str, ...], str, str]:
    name_key = _canon_key(blend.get("name"))
    children_with, children_without = _blend_child_payload(blend)
    child_names = sorted(
        {
            _canon_key(item.get("name"))
            for item in children_with
            if _canon_key(item.get("name"))
        }
        | {_canon_key(name) for name in children_without if _canon_key(name)}
    )
    blend_total_mg, _ = _blend_total_mg(blend)
    blend_total_key = "" if blend_total_mg is None else f"{round(blend_total_mg, 3):.3f}"
    source_path = _norm_text(_source_path_for_blend(blend))
    return (name_key, tuple(child_names), blend_total_key, source_path)


def _source_path_for_blend(blend: Dict[str, Any]) -> str:
    evidence = _safe_dict(blend.get("evidence"))
    source_raw = blend.get("source_field") or evidence.get("source_field") or blend.get("source_path") or ""
    source = str(source_raw).strip() if source_raw is not None else ""
    path = blend.get("source_path") or source
    return str(path).strip() if path is not None else ""


def _looks_like_blend_container_name(value: Any) -> bool:
    text = _norm_text(value)
    if not text:
        return False
    return any(token in text for token in ("blend", "complex", "matrix", "formula", "proprietary"))


def _sum_total_active_mg(product: Dict[str, Any]) -> float:
    total = 0.0
    for ing in get_active_ingredients(product):
        qty = _as_float(ing.get("quantity"), None)
        unit = _norm_text(ing.get("unit_normalized") or ing.get("unit"))
        if qty is None:
            continue
        if unit in {"mg", "milligram", "milligrams"}:
            total += qty
        elif unit in {"mcg", "ug", "microgram", "micrograms"}:
            total += qty / 1000.0
        elif unit in {"g", "gram", "grams"}:
            total += qty * 1000.0
    return total


def _quantity_to_mg(amount: Any, unit: Any) -> Tuple[Optional[float], bool]:
    qty = _as_float(amount, None)
    if qty is None:
        return None, False
    unit_norm = _norm_text(unit)
    if not unit_norm or unit_norm in {"mg", "milligram", "milligrams"}:
        return qty, False
    if unit_norm in {"mcg", "ug", "microgram", "micrograms"}:
        return qty / 1000.0, False
    if unit_norm in {"g", "gram", "grams"}:
        return qty * 1000.0, False
    return None, True


def _canon_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _norm_text(value)).strip()


def _fingerprint_to_string(fingerprint: Tuple[str, Tuple[str, ...], str, str]) -> str:
    return f"{fingerprint[0]}|{','.join(fingerprint[1])}|{fingerprint[2]}|{fingerprint[3]}"


def _negative_or_zero(value: float) -> float:
    if value <= 0:
        return 0.0
    return round(-float(value), 4)


def _clamp(min_value: float, max_value: float, value: float) -> float:
    return max(min_value, min(max_value, value))
