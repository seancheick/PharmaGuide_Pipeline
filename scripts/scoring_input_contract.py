#!/usr/bin/env python3
"""Version-neutral scoring input contract.

Scoring consumes cleaner/enrichment decisions from this module instead of
rediscovering active rows from labels or legacy raw fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional


SCORING_SOURCE = "ingredient_quality_data.ingredients_scorable"
LEGACY_IQD_SOURCE = "ingredient_quality_data.ingredients"
PRODUCT_EVIDENCE_SOURCE = "product_scoring_evidence"
PRODUCT_EVIDENCE_SCOPES = {"product_level", "blend_level", "row_level"}
PRODUCT_EVIDENCE_SECTION_SUPPORT = {
    "probiotic_cfu": ["probiotic_dose_adequacy"],
    "enzyme_activity": ["enzyme_activity_identity"],
    "sports_primary_dose": ["sports_primary_dose"],
    "omega_epa_dha_aggregate": ["omega_dose_adequacy", "omega_transparency"],
    "blend_anchor_mass": ["generic_blend_anchor_mass"],
    "percent_dv_dose": ["generic_percent_dv_dose"],
}
PRODUCT_EVIDENCE_ORIGINS = {"native_enrichment", "compatibility_derived"}
PRODUCT_EVIDENCE_REQUIRED_VALUE_FIELDS = {
    "evidence_type",
    "scoreable",
    "scoreable_identity",
    "score_eligible_by_cleaner",
    "dose_class",
    "dose_value",
    "dose_unit",
    "source",
    "raw_source_path",
    "evidence_scope",
    "linked_rows",
    "confidence",
    "reason",
    "scoring_parent_id",
    "evidence_canonical_id",
    "canonical_source_db",
    "evidence_origin",
}
PRODUCT_EVIDENCE_REQUIRED_PRESENT_FIELDS = {
    "clean_identity_id",
}

VALID_DOSE_CLASSES = {
    "therapeutic_mass",
    "enzyme_activity",
    "probiotic_cfu",
    "percent_dv_only",
}

VALID_NON_MASS_DOSE_CLASSES = {"enzyme_activity", "probiotic_cfu"}

_MASS_UNITS = {
    "mg", "milligram", "milligrams", "milligram(s)",
    "g", "gram", "grams", "gram(s)",
    "mcg", "ug", "µg", "μg", "microgram", "micrograms", "microgram(s)",
}
_SPORTS_PRIMARY_TYPES = {"protein_powder", "pre_workout", "sports"}
_PROTEIN_CANONICALS = {"protein", "whey_protein", "casein", "pea_protein", "rice_protein", "soy_protein"}
_SPORTS_PRIMARY_CANONICALS = _PROTEIN_CANONICALS | {
    "creatine_monohydrate",
    "beta-alanine",
    "beta_alanine",
    "l_citrulline",
    "hmb",
    "l_leucine",
    "l_isoleucine",
    "l_valine",
}
_PROBIOTIC_IDENTITY_TERMS = {
    "probiotic",
    "lactobacillus",
    "bifidobacterium",
    "streptococcus",
    "saccharomyces",
    "bacillus",
    "limosilactobacillus",
    "acidophilus",
    "dophilus",
    "bifidus",
    "cfu",
}
_PROBIOTIC_SUPPORT_CANONICALS = {"fiber", "prebiotics"}
_OMEGA_PRODUCT_TYPES = {"omega_3", "fish_oil"}
_OMEGA_EVIDENCE_CANONICALS = {
    "fish_oil",
    "fish_liver_oil",
    "cod_liver_oil",
    "krill_oil",
    "algal_oil",
    "algae_oil",
    "omega3",
    "omega_3",
    "omega_3_fatty_acids",
    "omega_fatty_acid_blend",
}
_NON_EPA_DHA_OMEGA_CANONICALS = {
    "ala",
    "alpha_linolenic_acid",
    "alpha_linolenic_acid_ala",
    "gla",
    "gamma_linolenic_acid",
    "cla",
    "conjugated_linoleic_acid",
    "oleic_acid",
}
_ENZYME_UNITS = {
    "alu", "ppi", "blgu", "hut", "sapu", "fip", "cu", "gdu", "dppiv", "dpp-iv",
    "lacu", "fccpu", "au", "skb", "mwu", "pu", "dp", "ckpu", "aju", "usp",
    "du", "pc", "agu", "bgu", "lu", "phy", "ftu", "su",
}
_ENZYME_ACTIVITY_RE = re.compile(
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>ALU|PPI|BLGU|HUT|SAPU|FIP|CU|GDU|DPP[- ]?IV|LACU|FCCPU|AU|SKB|MWU|PU|DP|CKPU|AJU|USP|DU|PC|AGU|BGU|LU|PHY|FTU|SU)(?:\b|$)",
    re.IGNORECASE,
)
_GENERIC_BLEND_IDENTITIES = {
    "",
    "blend",
    "blend_combination",
    "proprietary_blend",
    "proprietary_blend_combination",
    "proprietary_blend_herb_botanical",
    "general_proprietary_blends",
    "blend_general",
}

EXCLUDED_CLEANER_ROLES = {
    "blend_header_total",
    "nested_display_only",
    "composition_leaf",
    "source_descriptor",
    "nutrition_rollup",
    "excipient",
    "inactive",
    "label_header",
}

VALID_ACTIVE_ROLES = {"active_scorable", "active_misfiled_in_inactive"}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _primary_type(product: Dict[str, Any]) -> str:
    taxonomy = _safe_dict(product.get("supplement_taxonomy"))
    return _norm(product.get("primary_type") or taxonomy.get("primary_type"))


def _unit_is_mass(unit: Any) -> bool:
    return _norm(unit).replace(" ", "") in {u.replace(" ", "") for u in _MASS_UNITS}


def _positive_quantity(row: Dict[str, Any]) -> Optional[float]:
    for key in ("quantity", "amount", "dose", "dosage", "dose_value"):
        value = _as_float(row.get(key), None)
        if value is not None and value > 0:
            return value
    return None


def _positive_daily_value(row: Dict[str, Any]) -> Optional[float]:
    value = _as_float(row.get("daily_value") or row.get("dailyValue"), None)
    if value is not None and value > 0:
        return value
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    for variant in _safe_list(raw_taxonomy.get("quantityVariants")):
        if not isinstance(variant, dict):
            continue
        for target in _safe_list(variant.get("dailyValueTargetGroup")):
            if not isinstance(target, dict):
                continue
            value = _as_float(target.get("percent"), None)
            if value is not None and value > 0:
                return value
        value = _as_float(variant.get("daily_value"), None)
        if value is not None and value > 0:
            return value
    return None


def _row_text(row: Dict[str, Any]) -> str:
    pieces = [
        row.get("name"),
        row.get("standardName"),
        row.get("standard_name"),
        row.get("raw_source_text"),
        row.get("canonical_id"),
        row.get("category"),
        row.get("ingredientGroup"),
        row.get("notes"),
    ]
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    pieces.extend([
        raw_taxonomy.get("category"),
        raw_taxonomy.get("ingredientGroup"),
    ])
    for form in _safe_list(row.get("forms") or raw_taxonomy.get("forms")):
        if isinstance(form, dict):
            pieces.extend([form.get("name"), form.get("ingredientGroup"), form.get("category")])
        else:
            pieces.append(form)
    return " ".join(str(piece or "") for piece in pieces).strip()


def _row_identity_text(row: Dict[str, Any]) -> str:
    """Text that describes the row identity, excluding carrier/source forms.

    Form/source text can mention oils that carry a vitamin (for example
    "Vitamin A from cod liver oil"). That must not turn the vitamin dose into
    EPA/DHA evidence. Omega evidence is emitted only when the row itself is an
    omega/EPA/DHA/fish-oil identity.
    """
    pieces = [
        row.get("name"),
        row.get("standardName"),
        row.get("standard_name"),
        row.get("raw_source_text"),
        row.get("canonical_id"),
        row.get("category"),
        row.get("ingredientGroup"),
    ]
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    pieces.extend([
        raw_taxonomy.get("category"),
        raw_taxonomy.get("ingredientGroup"),
    ])
    return " ".join(str(piece or "") for piece in pieces).strip()


def _slug(value: Any) -> str:
    text = _norm(value)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _anchor_identity(row: Dict[str, Any]) -> tuple[str, Optional[str]]:
    canonical = _slug(row.get("canonical_id"))
    if canonical and canonical not in _GENERIC_BLEND_IDENTITIES and not canonical.startswith("blend_"):
        return canonical, row.get("name") or row.get("standardName")

    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    category = _norm(raw_taxonomy.get("category"))
    group = raw_taxonomy.get("ingredientGroup")
    group_slug = _slug(group)
    if (
        group_slug
        and group_slug not in _GENERIC_BLEND_IDENTITIES
        and not group_slug.startswith("proprietary_blend")
        and category != "blend"
    ):
        return group_slug, str(group)

    standard_name = row.get("standardName") or row.get("standard_name")
    standard_slug = _slug(standard_name)
    if standard_slug and standard_slug not in _GENERIC_BLEND_IDENTITIES and not standard_slug.startswith("proprietary_blend"):
        return standard_slug, str(standard_name)

    return "", None


def _is_botanical_or_standardized_anchor(row: Dict[str, Any]) -> bool:
    if _norm(row.get("canonical_source_db")) == "standardized_botanicals":
        return True
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    if _norm(raw_taxonomy.get("category")) == "botanical":
        return True
    for form in _safe_list(row.get("forms") or raw_taxonomy.get("forms")):
        if isinstance(form, dict) and _norm(form.get("category")) == "botanical":
            return True
    return False


def _evidence_base(
    *,
    row: Dict[str, Any],
    evidence_type: str,
    canonical_id: str,
    dose_value: float,
    dose_unit: str,
    evidence_scope: str,
    confidence: str,
    reason: str,
    name: Optional[str] = None,
    dose_class: str = "therapeutic_mass",
    clean_identity_id: Optional[str] = None,
    scoring_parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    raw_source_path = row.get("raw_source_path") or row.get("source") or evidence_type
    return {
        "evidence_type": evidence_type,
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": dose_class,
        "dose_value": dose_value,
        "dose_unit": dose_unit,
        "source": row.get("source_section") or "activeIngredients",
        "raw_source_path": raw_source_path,
        "evidence_scope": evidence_scope,
        "linked_rows": [str(raw_source_path)],
        "confidence": confidence,
        "reason": reason,
        "name": name or row.get("name") or row.get("raw_source_text") or evidence_type,
        "canonical_id": canonical_id,
        "clean_identity_id": clean_identity_id or _norm(row.get("canonical_id")) or None,
        "scoring_parent_id": scoring_parent_id or canonical_id,
        "evidence_canonical_id": canonical_id,
        "canonical_source_db": row.get("canonical_source_db") or "cleaned_active_ingredient",
        "evidence_origin": "compatibility_derived",
        "source_section": "product",
    }


def _has_epa_or_dha_signal(row: Dict[str, Any]) -> bool:
    text = _row_identity_text(row).lower()
    if re.search(r"\b(epa|dha)\b", text):
        return True
    if "eicosapentaenoic" in text or "docosahexaenoic" in text:
        return True
    return False


def _is_omega_aggregate_row(row: Dict[str, Any]) -> bool:
    text = _row_identity_text(row).lower()
    if any(
        token in text
        for token in (
            "omega-3",
            "omega 3",
            "omega3",
            "fish oil",
            "cod liver oil",
            "krill oil",
            "algae oil",
            "algal oil",
        )
    ):
        return True
    return bool(re.search(r"\b(epa|dha)\b", text))


def _can_emit_omega_aggregate_evidence(row: Dict[str, Any], canonical: str) -> bool:
    """True when the row identity itself can support EPA/DHA aggregate evidence."""
    if canonical.startswith("vitamin_") or canonical.startswith("mineral_"):
        return False
    if canonical in _OMEGA_EVIDENCE_CANONICALS:
        return True
    return not canonical and _is_omega_aggregate_row(row)


def _extract_enzyme_activity(row: Dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    unit = _norm(row.get("activity_unit") or row.get("unit"))
    value = _as_float(row.get("activity_value"), None)
    if unit in _ENZYME_UNITS and value and value > 0:
        return value, unit.upper()
    match = _ENZYME_ACTIVITY_RE.search(_row_text(row))
    if not match:
        return None, None
    parsed = _as_float(match.group("value").replace(",", ""), None)
    unit_text = match.group("unit").upper().replace(" ", "-")
    if unit_text == "DPP-IV":
        unit_text = "DPPIV"
    return parsed, unit_text


def _has_probiotic_identity_text(row: Dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in ("name", "standardName", "standard_name", "canonical_id", "raw_source_text", "category")
    )
    return any(term in text for term in _PROBIOTIC_IDENTITY_TERMS)


def _is_probiotic_support_row(row: Dict[str, Any]) -> bool:
    canonical = _norm(row.get("canonical_id"))
    if canonical in _PROBIOTIC_SUPPORT_CANONICALS:
        return True
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in ("name", "standardName", "standard_name", "raw_source_text", "category")
    )
    return any(term in text for term in ("dietary fiber", "prebiotic", "inulin", "fructooligosaccharide"))


def _has_non_probiotic_strict_active(product: Dict[str, Any]) -> bool:
    pdata = _safe_dict(product.get("probiotic_data"))
    probiotic_paths = {
        str(row.get("raw_source_path"))
        for row in _safe_list(pdata.get("probiotic_blends"))
        if isinstance(row, dict) and row.get("raw_source_path")
    }
    rows = []
    rows.extend(
        row for row in _safe_list(_safe_dict(product.get("ingredient_quality_data")).get("ingredients_scorable"))
        if isinstance(row, dict)
    )
    rows.extend(
        row for row in _safe_list(product.get("activeIngredients"))
        if isinstance(row, dict)
        and row.get("score_eligible_by_cleaner") is True
        and _norm(row.get("cleaner_row_role") or "active_scorable") == "active_scorable"
    )
    for row in rows:
        if str(row.get("raw_source_path") or "") in probiotic_paths:
            continue
        if _has_probiotic_identity_text(row):
            continue
        if _is_probiotic_support_row(row):
            continue
        if _norm(row.get("dose_class")) == "probiotic_cfu":
            continue
        return True
    return False


def _derive_probiotic_cfu_evidence(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pdata = _safe_dict(product.get("probiotic_data"))
    total_cfu = _as_float(pdata.get("total_cfu"), None)
    if total_cfu is None or total_cfu <= 0:
        billion = _as_float(pdata.get("total_billion_count"), None)
        total_cfu = (billion * 1_000_000_000) if billion and billion > 0 else None
    if total_cfu is None or total_cfu <= 0:
        return None

    primary_type = _primary_type(product)
    taxonomy_is_probiotic = primary_type == "probiotic"
    taxonomy_is_lagging = primary_type in {"", "general_supplement"}
    strain_count = int(_as_float(pdata.get("total_strain_count"), 0) or 0)
    has_probiotic_row_identity = bool(_safe_list(pdata.get("probiotic_blends"))) and strain_count > 0
    identity_proven = (
        bool(pdata.get("is_probiotic_product"))
        and (taxonomy_is_probiotic or (taxonomy_is_lagging and has_probiotic_row_identity))
        and has_probiotic_row_identity
        and not _has_non_probiotic_strict_active(product)
    )
    if not identity_proven:
        return None

    raw_source_path = pdata.get("cfu_raw_source_path")
    linked_rows = [str(path) for path in _safe_list(pdata.get("cfu_linked_rows")) if path]
    if raw_source_path and str(raw_source_path) not in linked_rows:
        linked_rows.append(str(raw_source_path))
    if not raw_source_path or not linked_rows:
        return None

    return _evidence_base(
        row={
            "raw_source_path": raw_source_path,
            "source_section": pdata.get("cfu_source") or "probiotic_data.total_cfu",
            "canonical_source_db": "probiotic_data",
        },
        evidence_type="probiotic_cfu",
        canonical_id="probiotic_cfu_total",
        dose_value=total_cfu,
        dose_unit="CFU",
        evidence_scope=_norm(pdata.get("cfu_evidence_scope")) or "product_level",
        confidence="high",
        reason="product_level_cfu_with_probiotic_identity",
        name="Total Probiotic CFU",
        dose_class="probiotic_cfu",
        clean_identity_id=None,
        scoring_parent_id="probiotic_cfu_total",
    )


def _sports_primary_identity_without_dose(row: Dict[str, Any], canonical: str) -> Dict[str, Any]:
    raw_source_path = row.get("raw_source_path") or row.get("source") or "sports_primary_identity"
    return {
        "evidence_type": "sports_primary_dose",
        "scoreable": False,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": bool(row.get("score_eligible_by_cleaner", True)),
        "dose_class": "therapeutic_mass",
        "dose_value": 0,
        "dose_unit": "",
        "source": row.get("source_section") or "activeIngredients",
        "raw_source_path": raw_source_path,
        "evidence_scope": "row_level",
        "linked_rows": [str(raw_source_path)],
        "confidence": "low",
        "reason": "sports_primary_identity_without_disclosed_dose",
        "rejection_reason": "missing_primary_sports_dose",
        "name": row.get("name") or row.get("raw_source_text") or "Sports primary active",
        "canonical_id": canonical,
        "clean_identity_id": canonical or None,
        "scoring_parent_id": canonical,
        "evidence_canonical_id": canonical,
        "canonical_source_db": row.get("canonical_source_db") or "cleaned_active_ingredient",
        "evidence_origin": "compatibility_derived",
        "source_section": "product",
    }


def derive_product_scoring_evidence(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Derive ScoringEvidence v1 rows from cleaner/enrichment-owned fields.

    This adapter is the compatibility bridge for existing enriched artifacts.
    Future enrichment runs stamp these rows into product_scoring_evidence, but
    v3/v4 scoring still consume them through get_scoring_ingredients().
    """
    product = product or {}
    evidence: List[Dict[str, Any]] = []
    ptype = _primary_type(product)
    active_rows = [row for row in _safe_list(product.get("activeIngredients")) if isinstance(row, dict)]
    scorable_paths = {
        str(row.get("raw_source_path"))
        for row in _safe_list(_safe_dict(product.get("ingredient_quality_data")).get("ingredients_scorable"))
        if (
            isinstance(row, dict)
            and row.get("raw_source_path")
            and (
                _norm(row.get("dose_class")) in VALID_NON_MASS_DOSE_CLASSES
                or row.get("has_dose") is True
                or (
                    _positive_quantity(row) is not None
                    and _unit_is_mass(row.get("unit") or row.get("unit_normalized") or row.get("dose_unit"))
                )
            )
        )
    }
    special_evidence_paths: set[str] = set()
    has_explicit_epa_dha_row = any(
        _norm(row.get("canonical_id")) in {"epa", "dha", "epa_dha"}
        and _positive_quantity(row) is not None
        and _unit_is_mass(row.get("unit") or row.get("unit_normalized") or row.get("dose_unit"))
        for row in active_rows
    )

    for row in active_rows:
        quantity = _positive_quantity(row)
        unit = row.get("unit") or row.get("unit_normalized") or row.get("dose_unit")
        canonical = _norm(row.get("canonical_id"))
        anchor_canonical, anchor_name = _anchor_identity(row)
        text = _row_text(row).lower()
        if (
            ptype in _SPORTS_PRIMARY_TYPES
            and quantity is not None
            and _unit_is_mass(unit)
            and (canonical in _PROTEIN_CANONICALS or "protein" in text)
            and str(row.get("raw_source_path") or "") not in scorable_paths
        ):
            special_evidence_paths.add(str(row.get("raw_source_path") or ""))
            evidence.append(_evidence_base(
                row=row,
                evidence_type="sports_primary_dose",
                canonical_id="protein",
                clean_identity_id=canonical or None,
                scoring_parent_id="protein",
                dose_value=quantity,
                dose_unit=str(unit),
                evidence_scope="row_level",
                confidence="high",
                reason="protein_macro_or_primary_sports_dose",
                name=row.get("name") or "Protein",
            ))
        elif (
            ptype in _SPORTS_PRIMARY_TYPES
            and canonical in _SPORTS_PRIMARY_CANONICALS
            and str(row.get("raw_source_path") or "") not in scorable_paths
        ):
            special_evidence_paths.add(str(row.get("raw_source_path") or ""))
            evidence.append(_sports_primary_identity_without_dose(row, canonical))

        if (
            not has_explicit_epa_dha_row
            and
            (ptype in _OMEGA_PRODUCT_TYPES or _is_omega_aggregate_row(row))
            and quantity is not None
            and _unit_is_mass(unit)
            and _is_omega_aggregate_row(row)
            and (_can_emit_omega_aggregate_evidence(row, canonical) or _has_epa_or_dha_signal(row))
            and canonical not in {"epa", "dha", "epa_dha"}
            and canonical not in _NON_EPA_DHA_OMEGA_CANONICALS
        ):
            special_evidence_paths.add(str(row.get("raw_source_path") or ""))
            evidence.append(_evidence_base(
                row=row,
                evidence_type="omega_epa_dha_aggregate",
                canonical_id="epa_dha",
                clean_identity_id=canonical or None,
                scoring_parent_id="epa_dha",
                dose_value=quantity,
                dose_unit=str(unit),
                evidence_scope="row_level",
                confidence="medium" if _has_epa_or_dha_signal(row) else "low",
                reason="omega_epa_dha_aggregate_from_label_row",
                name=row.get("name") or "EPA/DHA aggregate",
            ))

        activity_value, activity_unit = _extract_enzyme_activity(row)
        if activity_value is not None and activity_unit:
            special_evidence_paths.add(str(row.get("raw_source_path") or ""))
            evidence.append(_evidence_base(
                row=row,
                evidence_type="enzyme_activity",
                canonical_id=canonical or "digestive_enzymes",
                clean_identity_id=canonical or None,
                scoring_parent_id=canonical or "digestive_enzymes",
                dose_value=activity_value,
                dose_unit=activity_unit,
                evidence_scope="row_level",
                confidence="high",
                reason="enzyme_activity_unit_from_label_notes",
                name=row.get("name") or "Enzyme activity",
                dose_class="enzyme_activity",
            ))

        cleaner_role = _norm(row.get("cleaner_row_role"))
        anchor_reason = ""
        daily_value = _positive_daily_value(row)
        if (
            daily_value is not None
            and quantity is not None
            and not _unit_is_mass(unit)
            and anchor_canonical
            and str(row.get("raw_source_path") or "") not in scorable_paths
            and str(row.get("raw_source_path") or "") not in special_evidence_paths
        ):
            special_evidence_paths.add(str(row.get("raw_source_path") or ""))
            item = _evidence_base(
                row=row,
                evidence_type="percent_dv_dose",
                canonical_id=anchor_canonical,
                clean_identity_id=canonical or None,
                scoring_parent_id=anchor_canonical,
                dose_value=daily_value,
                dose_unit="%DV",
                evidence_scope="row_level",
                confidence="medium",
                reason="percent_daily_value_dose_without_mass_unit",
                name=anchor_name or row.get("name") or "Percent DV dose",
                dose_class="percent_dv_only",
            )
            if _is_botanical_or_standardized_anchor(row):
                item["anchor_risk_class"] = "botanical_or_standardized"
            evidence.append(item)

        if (
            cleaner_role in {"blend_header_total", "active_scorable"}
            and quantity is not None
            and _unit_is_mass(unit)
            and anchor_canonical
            and str(row.get("raw_source_path") or "") not in scorable_paths
            and (
                cleaner_role == "blend_header_total"
                or str(row.get("raw_source_path") or "") not in special_evidence_paths
            )
        ):
            anchor_reason = (
                "identity_bearing_blend_header_mass"
                if cleaner_role == "blend_header_total"
                else "identity_bearing_active_anchor_mass"
            )
            item = _evidence_base(
                row=row,
                evidence_type="blend_anchor_mass",
                canonical_id=anchor_canonical,
                clean_identity_id=canonical or None,
                scoring_parent_id=anchor_canonical,
                dose_value=quantity,
                dose_unit=str(unit),
                evidence_scope="blend_level" if cleaner_role == "blend_header_total" else "row_level",
                confidence="medium",
                reason=anchor_reason,
                name=anchor_name or row.get("name") or "Anchor mass",
            )
            if _is_botanical_or_standardized_anchor(row):
                item["anchor_risk_class"] = "botanical_or_standardized"
            evidence.append(item)

    probiotic_cfu_evidence = _derive_probiotic_cfu_evidence(product)
    if probiotic_cfu_evidence:
        evidence.append(probiotic_cfu_evidence)

    # Deduplicate by evidence type + provenance + dose. Native evidence rows are
    # deduped later with these derived rows, so this only keeps the adapter tidy.
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in evidence:
        key = (
            item.get("evidence_type"),
            item.get("canonical_id"),
            item.get("raw_source_path"),
            item.get("dose_value"),
            item.get("dose_unit"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


@dataclass
class ScoringFallback:
    fallback_class: str
    fallback_reason: str
    source: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "fallback_class": self.fallback_class,
            "fallback_reason": self.fallback_reason,
            "source": self.source,
        }


@dataclass
class RejectedScoringRow:
    row: Dict[str, Any]
    reason: str
    missing_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.row.get("name") or self.row.get("standard_name"),
            "canonical_id": self.row.get("canonical_id"),
            "reason": self.reason,
            "missing_fields": list(self.missing_fields),
            "raw_source_path": self.row.get("raw_source_path"),
            "cleaner_row_role": self.row.get("cleaner_row_role"),
            "role_classification": self.row.get("role_classification"),
        }


@dataclass
class ScoringInputResult:
    rows: List[Dict[str, Any]]
    rejected_rows: List[RejectedScoringRow]
    source: str
    fallbacks_used: List[ScoringFallback]
    strict_contract_passed: bool
    zero_scorable_reason: Optional[str]
    mapped_count: int
    unmapped_count: int
    mapped_coverage: Optional[float]
    contract_findings: List[str]
    mapped_coverage_applicable: bool = True

    @property
    def unmapped_actives(self) -> List[str]:
        names: List[str] = []
        for rejected in self.rejected_rows:
            if rejected.reason == "missing_scoring_identity":
                row = rejected.row
                names.append(
                    row.get("name")
                    or row.get("standard_name")
                    or row.get("raw_source_text")
                    or "unknown"
                )
        return names

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "scoring_ingredients_source": self.source,
            "iqd_ingredients_fallback_used": any(
                fallback.source == LEGACY_IQD_SOURCE for fallback in self.fallbacks_used
            ),
            "ingredients_scorable_count": self.mapped_count + self.unmapped_count,
            "scoring_rows_count": len(self.rows),
            "rejected_rows_count": len(self.rejected_rows),
            "rejected_rows": [row.to_dict() for row in self.rejected_rows[:25]],
            "scoring_fallbacks_used": [fallback.to_dict() for fallback in self.fallbacks_used],
            "strict_contract_passed": self.strict_contract_passed,
            "strict_scoring_contract": {
                "passed": self.strict_contract_passed,
                "findings": list(self.contract_findings),
                "zero_scorable_reason": self.zero_scorable_reason,
                "mapped_coverage_applicable": self.mapped_coverage_applicable,
            },
            "zero_scorable_reason": self.zero_scorable_reason,
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
            "mapped_coverage": self.mapped_coverage,
            "mapped_coverage_applicable": self.mapped_coverage_applicable,
            "contract_findings": list(self.contract_findings),
        }


def _has_identity(row: Dict[str, Any]) -> bool:
    if row.get("mapped_identity") is False:
        return False
    return bool(
        row.get("canonical_id")
        or row.get("mapped_identity")
        or row.get("matched_target")
        or row.get("matched_alias")
        or row.get("mapped") is True
    )


def _has_dose_evidence(row: Dict[str, Any]) -> bool:
    dose_class = _norm(row.get("dose_class"))
    if dose_class in VALID_NON_MASS_DOSE_CLASSES:
        return True
    if row.get("has_dose") is True:
        return True
    quantity = _as_float(
        row.get("quantity", row.get("amount", row.get("dose", row.get("dosage")))),
        None,
    )
    if quantity is None or quantity <= 0:
        return False
    unit = _norm(
        row.get("unit")
        or row.get("unit_normalized")
        or row.get("normalized_unit")
        or row.get("dose_unit")
    )
    return unit not in {"", "np", "n/a", "na", "none", "0"}


def _missing_product_evidence_fields(item: Dict[str, Any]) -> List[str]:
    missing = [
        field_name
        for field_name in PRODUCT_EVIDENCE_REQUIRED_VALUE_FIELDS
        if item.get(field_name) in (None, "", [])
    ]
    missing.extend(
        field_name
        for field_name in PRODUCT_EVIDENCE_REQUIRED_PRESENT_FIELDS
        if field_name not in item
    )
    if item.get("scoreable") is not True:
        missing.append("scoreable")
    if item.get("scoreable_identity") is not True:
        missing.append("scoreable_identity")
    if item.get("score_eligible_by_cleaner") is not True:
        missing.append("score_eligible_by_cleaner")
    dose_value = _as_float(item.get("dose_value"), None)
    if dose_value is None or dose_value <= 0:
        missing.append("dose_value")
    if _norm(item.get("evidence_scope")) not in PRODUCT_EVIDENCE_SCOPES:
        missing.append("evidence_scope")
    if _norm(item.get("evidence_origin")) not in PRODUCT_EVIDENCE_ORIGINS:
        missing.append("evidence_origin")
    return sorted(set(missing))


def _product_scoring_evidence_rows(
    product: Dict[str, Any],
    *,
    strict: bool,
) -> tuple[List[Dict[str, Any]], List[RejectedScoringRow], List[str]]:
    evidence = product.get("product_scoring_evidence")
    if isinstance(evidence, dict):
        evidence_rows = _safe_list(evidence.get("items") or evidence.get("evidence"))
        if not evidence_rows and evidence:
            evidence_rows = [evidence]
    else:
        evidence_rows = _safe_list(evidence)
    evidence_rows = [item for item in evidence_rows if isinstance(item, dict)]
    evidence_rows.extend(derive_product_scoring_evidence(product))

    rows: List[Dict[str, Any]] = []
    rejected: List[RejectedScoringRow] = []
    findings: List[str] = []
    seen_rows = set()
    for idx, item in enumerate(evidence_rows):
        if not isinstance(item, dict):
            continue
        evidence_type = _norm(item.get("evidence_type") or item.get("dose_class"))
        dose_class = _norm(item.get("dose_class"))
        if item.get("scoreable") is False:
            rejected.append(_reject(item, f"product_evidence_not_scoreable:{item.get('rejection_reason') or 'rejected_by_enrichment'}"))
            continue
        if evidence_type not in PRODUCT_EVIDENCE_SECTION_SUPPORT:
            if item.get("scoreable") is True:
                findings.append(f"invalid_product_evidence_type:{evidence_type or dose_class or idx}")
            continue
        if dose_class not in VALID_DOSE_CLASSES:
            if item.get("scoreable") is True:
                findings.append(f"invalid_product_evidence_dose_class:{evidence_type}:{dose_class or idx}")
            continue
        missing = _missing_product_evidence_fields(item)
        dose_value = _as_float(item.get("dose_value"), None)
        if missing:
            rejected.append(_reject(item, "malformed_product_scoring_evidence", sorted(set(missing))))
            if strict:
                findings.append(f"malformed_product_scoring_evidence:{idx}:{','.join(sorted(set(missing)))}")
            continue

        row = {
            **item,
            "name": item.get("name") or item.get("label") or evidence_type,
            "canonical_id": item.get("canonical_id") or item.get("evidence_canonical_id") or evidence_type,
            "mapped": item.get("mapped", True),
            "mapped_identity": item.get("mapped_identity", True),
            "scoreable_identity": True,
            "role_classification": "active_scorable",
            "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True,
            "dose_class": dose_class,
            "quantity": dose_value,
            "unit": item.get("dose_unit"),
            "source_section": item.get("source_section") or PRODUCT_EVIDENCE_SOURCE,
            "scoring_input_kind": "product_level_evidence",
            "section_support": PRODUCT_EVIDENCE_SECTION_SUPPORT[evidence_type],
            "generic_form_quality_credit": bool(item.get("generic_form_quality_credit", False)),
        }
        dedupe_key = (
            row.get("evidence_type"),
            row.get("canonical_id"),
            row.get("raw_source_path"),
            row.get("quantity"),
            row.get("unit"),
        )
        if dedupe_key in seen_rows:
            continue
        seen_rows.add(dedupe_key)
        rows.append(row)
    return rows, rejected, findings


def _reject(row: Dict[str, Any], reason: str, missing_fields: Optional[List[str]] = None) -> RejectedScoringRow:
    return RejectedScoringRow(row=row, reason=reason, missing_fields=missing_fields or [])


def _evaluate_row(row: Dict[str, Any], *, strict: bool) -> tuple[bool, Optional[RejectedScoringRow], List[str]]:
    findings: List[str] = []
    missing: List[str] = []
    for field_name in (
        "source_section",
        "raw_source_path",
        "cleaner_row_role",
        "score_eligible_by_cleaner",
        "dose_class",
        "role_classification",
        "scoreable_identity",
    ):
        if field_name not in row:
            missing.append(field_name)
    if strict and missing:
        findings.append(f"missing_required_fields:{','.join(missing)}")

    cleaner_role = _norm(row.get("cleaner_row_role"))
    if cleaner_role in EXCLUDED_CLEANER_ROLES:
        return False, _reject(row, f"excluded_cleaner_role:{cleaner_role}"), findings
    if row.get("is_blend_header") or row.get("blend_total_weight_only"):
        return False, _reject(row, "excluded_blend_total_or_header"), findings
    if row.get("is_proprietary_blend") and not _has_identity(row):
        return False, _reject(row, "excluded_unmapped_proprietary_blend"), findings

    if row.get("score_eligible_by_cleaner") is False:
        return False, _reject(row, "cleaner_marked_not_score_eligible"), findings

    role = _norm(row.get("role_classification") or cleaner_role)
    if role and role not in VALID_ACTIVE_ROLES:
        return False, _reject(row, f"excluded_role_classification:{role}"), findings

    if row.get("scoreable_identity") is False:
        return False, _reject(row, "identity_marked_not_scoreable"), findings

    if not _has_dose_evidence(row):
        return False, _reject(row, "missing_dose_evidence"), findings

    if not _has_identity(row):
        return False, _reject(row, "missing_scoring_identity"), findings

    return True, None, findings


def get_scoring_ingredients(
    product: Dict[str, Any],
    *,
    strict: bool = True,
    allow_legacy_fallback: bool = False,
) -> ScoringInputResult:
    """Return the single validated scoring input contract for v3 and v4.

    Strict mode never silently falls back to legacy IQD/raw active rows.
    Missing cleaner/enrichment fields are surfaced as contract findings so
    release audits can fail current artifacts while old unit fixtures remain
    inspectable during migration.
    """
    product = product or {}
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    source = SCORING_SOURCE
    fallbacks: List[ScoringFallback] = []
    contract_findings: List[str] = []

    if strict and not isinstance(iqd.get("ingredients_scorable"), list):
        contract_findings.append("missing_iqd_ingredients_scorable_list")
    candidates = [row for row in _safe_list(iqd.get("ingredients_scorable")) if isinstance(row, dict)]
    product_evidence_rows, product_evidence_rejected, product_evidence_findings = _product_scoring_evidence_rows(
        product,
        strict=strict,
    )
    if product_evidence_rows:
        candidates.extend(product_evidence_rows)
        source = f"{SCORING_SOURCE}+{PRODUCT_EVIDENCE_SOURCE}"
    rejected: List[RejectedScoringRow] = list(product_evidence_rejected)
    contract_findings.extend(product_evidence_findings)

    if not candidates and allow_legacy_fallback:
        legacy = [row for row in _safe_list(iqd.get("ingredients")) if isinstance(row, dict)]
        if legacy:
            candidates = legacy
            source = LEGACY_IQD_SOURCE
            fallbacks.append(ScoringFallback(
                fallback_class="old_batch_compatibility",
                fallback_reason="ingredients_scorable_empty_used_legacy_iqd_ingredients",
                source=LEGACY_IQD_SOURCE,
            ))
    rows: List[Dict[str, Any]] = []
    row_findings: List[str] = []
    for row in candidates:
        ok, rejection, findings = _evaluate_row(row, strict=strict)
        row_findings.extend(findings)
        if ok:
            rows.append(row)
        elif rejection is not None:
            rejected.append(rejection)

    unmapped_count = sum(1 for item in rejected if item.reason == "missing_scoring_identity")
    mapped_count = len(rows)
    denominator = mapped_count + unmapped_count
    mapped_coverage = (mapped_count / denominator) if denominator else 0.0

    contract_findings.extend(sorted(set(row_findings)))
    if strict and fallbacks:
        contract_findings.append("strict_mode_used_legacy_fallback")

    zero_reason: Optional[str] = None
    if not rows:
        if not candidates:
            zero_reason = "no_strict_scoring_candidates"
        elif rejected:
            zero_reason = "all_scoring_candidates_rejected"
        else:
            zero_reason = "no_scorable_rows"

    strict_passed = not contract_findings and not fallbacks
    return ScoringInputResult(
        rows=rows,
        rejected_rows=rejected,
        source=source,
        fallbacks_used=fallbacks,
        strict_contract_passed=strict_passed,
        zero_scorable_reason=zero_reason,
        mapped_count=mapped_count,
        unmapped_count=unmapped_count,
        mapped_coverage=mapped_coverage,
        contract_findings=contract_findings,
    )


def is_nutrition_only_product(product: Dict[str, Any], *, allow_legacy_keyword_fallback: bool = False) -> bool:
    """Return True only for explicit enrichment/taxonomy nutrition-only facts.

    Keyword fallback is retained for old batches when callers explicitly opt in.
    """
    product = product or {}
    for value in (
        product.get("product_scoring_class"),
        _safe_dict(product.get("supplement_taxonomy")).get("product_scoring_class"),
        _safe_dict(product.get("scoring_contract")).get("product_scoring_class"),
    ):
        if _norm(value) == "nutrition_only":
            return True

    if not allow_legacy_keyword_fallback:
        return False

    name = _norm(product.get("product_name") or product.get("fullName"))
    return any(
        keyword in name
        for keyword in (
            "whey",
            "casein",
            "pea protein",
            "soy protein",
            "rice protein",
            "hemp protein",
            "plant protein",
            "plant-based protein",
            "protein powder",
            "protein shake",
            "protein blend",
            "meal replacement",
            "mass gainer",
            "weight gainer",
            "smoothie mix",
        )
    )


# ---------------------------------------------------------------------------
# V4 Phase 2 — ingredient role classification (compatibility mode)
#
# Deterministic, scoring-time role assignment so the completeness gate
# (Phase 3) can stop capping products for *adjunct* data gaps. CLASSIFY ONLY:
# this code changes no score, cap, or verdict. Caps are decided in Phase 3.
#
# Level -> role precedence (first match wins); user-approved Option 1:
#   L1 drives selected module    -> primary         (router driver canonical)
#   L2 named in product title    -> claim_prominent (role_source=product_name)
#   L3 front-label claim         -> INERT (no data source today; never emitted)
#   L4 required for subtype       -> major          (multi micronutrient panel)
#   L5 high comparable-unit mass  -> major
#   L6 otherwise                  -> adjunct
#
# Spec: docs/superpowers/specs/2026-05-31-v4-role-classification-design.md
# ---------------------------------------------------------------------------

ROLE_PRIMARY = "primary"
ROLE_CLAIM_PROMINENT = "claim_prominent"
ROLE_MAJOR = "major"
ROLE_ADJUNCT = "adjunct"

# Tokens too generic to prove a product is "about" an ingredient when found in
# the title. Without these, "Vitamin C" would match "Daily Multivitamin".
_ROLE_TITLE_STOPWORDS = {
    "root", "leaf", "extract", "powder", "complex", "blend", "acid", "oil",
    "capsule", "tablet", "softgel", "organic", "pure", "strength", "daily",
    "formula", "support", "vitamin", "mineral", "multivitamin", "women",
    "womens", "men", "mens", "with", "plus", "high", "ultra",
}

# Fraction of the largest comparable-unit (mass) row a row must reach to count
# as a "major" formulation component by mass alone (L5).
_ROLE_MASS_MAJOR_FRACTION = 0.25


def _role_mass_mg(row: Dict[str, Any]) -> Optional[float]:
    """Return the row's mass in mg, or None when not a comparable mass unit.

    IU and activity units (CFU, enzyme activity) are intentionally NOT
    mass-comparable and return None so they never drive the L5 mass ratio.
    """
    qty = _positive_quantity(row)
    if qty is None:
        return None
    unit = _norm(
        row.get("unit")
        or row.get("unit_normalized")
        or row.get("normalized_unit")
        or row.get("dose_unit")
    ).replace(" ", "")
    if unit in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return qty
    if unit in {"g", "gram", "grams", "gram(s)"}:
        return qty * 1000.0
    if unit in {"mcg", "ug", "µg", "μg", "microgram", "micrograms", "microgram(s)"}:
        return qty / 1000.0
    return None


def _role_driver_canonicals(module: str) -> set:
    """Module driver canonical IDs, sourced from the router (single source of
    truth). Lazy import avoids the router<->contract circular import at load."""
    try:
        from scoring_v4 import router as _router  # lazy: router imports this module
    except ImportError:  # pragma: no cover - router optional at import time
        return set()
    if module == "omega":
        # EPA/DHA AND the fish-oil/krill/algal parents that route a product to
        # the omega module — a parent-only row is still the module driver. (WR-01)
        return set(_router._OMEGA_INGREDIENT_CANONICALS) | set(_router._OMEGA_PARENT_CANONICALS)
    if module == "sports":
        return (
            set(_router._SPORTS_PROTEIN_CANONICALS)
            | set(_router._SPORTS_SINGLE_CANONICALS)
            | set(_router._BCAA_CANONICALS)
            | set(_router._EAA_CANONICALS)
        )
    return set()


def _role_is_blend_member(row: Dict[str, Any]) -> bool:
    return bool(
        row.get("is_proprietary_blend")
        or row.get("is_blend_header")
        or row.get("blend_total_weight_only")
    )


def _role_is_probiotic_strain(row: Dict[str, Any]) -> bool:
    if _norm(row.get("dose_class")) == "probiotic_cfu":
        return True
    return "cfu" in _norm(row.get("unit") or row.get("dose_unit"))


def _named_in_title(row: Dict[str, Any], title_norm: str) -> bool:
    if not title_norm:
        return False
    # Whole-token match, NOT substring: "iron" must not match inside
    # "environmental". (CR-01)
    title_tokens = {tok for tok in re.split(r"[^a-z0-9]+", title_norm) if tok}
    candidates = (
        _norm(row.get("name")),
        _norm(row.get("standardName")),
        _norm(row.get("standard_name")),
        _norm(row.get("canonical_id")).replace("_", " "),
    )
    for cand in candidates:
        for token in re.split(r"[^a-z0-9]+", cand):
            if len(token) >= 4 and token not in _ROLE_TITLE_STOPWORDS and token in title_tokens:
                return True
    return False


def _role_context(
    product: Dict[str, Any],
    module: Optional[str],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if module is None:
        try:
            from scoring_v4.router import class_for_product  # lazy
        except ImportError:  # pragma: no cover
            module = "generic"
        else:
            module = class_for_product(product)
    masses = [m for m in (_role_mass_mg(r) for r in rows) if m is not None]
    return {
        "module": module,
        "title_norm": _norm(product.get("product_name") or product.get("fullName")),
        "driver_canonicals": _role_driver_canonicals(module),
        "max_mass_mg": max(masses) if masses else 0.0,
    }


def _classify_one(row: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    canonical = _norm(row.get("canonical_id"))
    module = ctx["module"]

    def out(role: str, reason: str, source: str, confidence: str) -> Dict[str, Any]:
        return {
            "canonical_id": row.get("canonical_id"),
            "name": row.get("name"),
            "role": role,
            "role_reason": reason,
            "role_source": source,
            "role_confidence": confidence,
        }

    # L1 — drives the selected module. A driver is primary even with no
    # disclosed dose; Phase 3 owns the missing-primary-dose cap, so the role
    # must still surface the driver rather than hide it. (WR-02)
    if canonical and canonical in ctx["driver_canonicals"]:
        return out(ROLE_PRIMARY, f"drives_module_{module}", "router_driver", "high")
    if module == "probiotic" and _role_is_probiotic_strain(row):
        return out(ROLE_PRIMARY, "drives_module_probiotic", "router_driver", "high")

    # L2 — named in the product title. (L3 front-label-claim has no data source
    # today and is intentionally NOT emitted — no fabricated claim provenance.)
    if _named_in_title(row, ctx["title_norm"]):
        return out(ROLE_CLAIM_PROMINENT, "named_in_product_title", "product_name", "high")

    is_blend = _role_is_blend_member(row)
    mass_mg = _role_mass_mg(row)

    # L4 — required for subtype: micronutrient panel members of a multi/prenatal.
    # Panel members are mass-dosed; a CFU probiotic add-on is NOT mass-dosed and
    # so stays adjunct, so Phase 3 won't cap a multi for an adjunct's data gap.
    if module == "multi_or_prenatal" and mass_mg is not None and not is_blend:
        return out(ROLE_MAJOR, "multi_panel_member", "module_subtype", "medium")

    # L5 — high comparable-unit mass ratio
    if (
        mass_mg is not None
        and not is_blend
        and ctx["max_mass_mg"] > 0
        and mass_mg >= _ROLE_MASS_MAJOR_FRACTION * ctx["max_mass_mg"]
    ):
        return out(ROLE_MAJOR, "high_comparable_mass_ratio", "mass_ratio", "medium")

    # L6 — residual
    return out(ROLE_ADJUNCT, "residual_adjunct", "default", "medium")


def classify_ingredient_roles(
    product: Dict[str, Any],
    *,
    module: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Classify every scoring row's role (compatibility mode, Phase 2).

    Returns one provenance dict per row in
    ``get_scoring_ingredients(product).rows`` order. CLASSIFY ONLY — changes no
    score, cap, or verdict. When ``module`` is omitted it is resolved via the
    router (``class_for_product``).
    """
    product = product or {}
    rows = get_scoring_ingredients(product, strict=True).rows
    ctx = _role_context(product, module, rows)
    return [_classify_one(row, ctx) for row in rows]


def classify_ingredient_role(
    product: Dict[str, Any],
    row: Dict[str, Any],
    *,
    module: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify a single scoring ``row`` within ``product``.

    Convenience wrapper around :func:`classify_ingredient_roles`; builds the
    same product-level context (module, title, mass denominator).

    NOTE: this rebuilds the full contract + context on every call. For batch
    use (e.g. classifying every row of a product) call
    :func:`classify_ingredient_roles` once instead — looping this is O(n^2). (WR-04)
    """
    product = product or {}
    rows = get_scoring_ingredients(product, strict=True).rows
    ctx = _role_context(product, module, rows)
    return _classify_one(row, ctx)
