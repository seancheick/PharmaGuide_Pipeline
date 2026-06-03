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
SCORING_CLASSIFICATION_SCHEMA_VERSION = "1.0.0"
SCORING_CLASSIFICATION_ORIGINS = {"compatibility_derived", "native_enrichment"}
SCORING_ROUTE_MODULES = {"generic", "probiotic", "multi_or_prenatal", "omega", "sports"}
SCORING_ROUTE_CONFIDENCE = {"high", "medium", "low", "failed"}
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


def _has_omega_identity_text(row: Dict[str, Any]) -> bool:
    canonical = _slug(row.get("canonical_id"))
    if canonical in _OMEGA_EVIDENCE_CANONICALS or canonical in {"epa", "dha", "epa_dha"}:
        return True
    text = _row_identity_text(row).lower()
    return any(
        term in text
        for term in (
            "eicosapentaenoic",
            "docosahexaenoic",
            "fish oil",
            "omega-3",
            "omega 3",
            "omega3",
            "epa",
            "dha",
        )
    )


def _recoverable_nested_identity(row: Dict[str, Any]) -> bool:
    """True when a display-only nested row carries identity v4 can score.

    This is a compatibility bridge for stale enriched artifacts where the
    cleaner retained a child active under a blend/header but enrichment excluded
    it from `ingredients_scorable`. It does not parse labels or product names,
    and it does not invent dose; it only preserves an already-resolved child
    identity so modules can score it with the appropriate disclosure penalty.
    """
    canonical, _ = _anchor_identity(row)
    if not canonical:
        return False
    return (
        _has_probiotic_identity_text(row)
        or _has_omega_identity_text(row)
        or _is_botanical_or_standardized_anchor(row)
    )


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


def _is_nested_under(parent_path: str, row: Dict[str, Any]) -> bool:
    child_path = str(row.get("raw_source_path") or "")
    return bool(parent_path and child_path.startswith(f"{parent_path}.nestedRows["))


def _identity_named_in_product_title(product: Dict[str, Any], row: Dict[str, Any]) -> bool:
    title_tokens = {
        token
        for token in re.split(
            r"[^a-z0-9]+",
            _norm(product.get("product_name") or product.get("fullName")),
        )
        if len(token) >= 4
    }
    if not title_tokens:
        return False
    identity_tokens: set[str] = set()
    for value in (
        row.get("name"),
        row.get("standardName"),
        row.get("standard_name"),
        row.get("raw_source_text"),
        row.get("canonical_id"),
    ):
        identity_tokens.update(
            token
            for token in re.split(r"[^a-z0-9]+", _norm(value).replace("_", " "))
            if len(token) >= 4
        )
    return bool(title_tokens & identity_tokens)


def _best_nested_anchor_child(
    product: Dict[str, Any],
    parent: Dict[str, Any],
    candidate_rows: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    parent_path = str(parent.get("raw_source_path") or "")
    children = [
        row
        for row in candidate_rows
        if _is_nested_under(parent_path, row) and _anchor_identity(row)[0]
        and not _has_probiotic_identity_text(row)
    ]
    if not children:
        return None
    title_matches = [row for row in children if _identity_named_in_product_title(product, row)]
    if title_matches:
        return title_matches[0]
    return children[0]


def _derive_blend_header_anchor_from_nested_child(
    product: Dict[str, Any],
    parent: Dict[str, Any],
    candidate_rows: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    cleaner_role = _norm(parent.get("cleaner_row_role"))
    if cleaner_role != "blend_header_total" and not parent.get("blend_total_weight_only"):
        return None
    quantity = _positive_quantity(parent)
    unit = parent.get("unit") or parent.get("unit_normalized") or parent.get("dose_unit")
    if quantity is None or not _unit_is_mass(unit):
        return None

    child = _best_nested_anchor_child(product, parent, candidate_rows)
    if not child:
        return None
    anchor_canonical, anchor_name = _anchor_identity(child)
    if not anchor_canonical:
        return None

    title_match = _identity_named_in_product_title(product, child)
    item = _evidence_base(
        row=parent,
        evidence_type="blend_anchor_mass",
        canonical_id=anchor_canonical,
        clean_identity_id=_norm(child.get("canonical_id")) or anchor_canonical,
        scoring_parent_id=anchor_canonical,
        dose_value=quantity,
        dose_unit=str(unit),
        evidence_scope="blend_level",
        confidence="medium" if title_match else "low",
        reason="identity_bearing_blend_header_mass_from_nested_child",
        name=anchor_name or child.get("name") or "Blend anchor mass",
    )
    child_path = str(child.get("raw_source_path") or "")
    if child_path and child_path not in item["linked_rows"]:
        item["linked_rows"].append(child_path)
    item["canonical_source_db"] = child.get("canonical_source_db") or item["canonical_source_db"]
    if _is_botanical_or_standardized_anchor(child):
        item["anchor_risk_class"] = "botanical_or_standardized"
    return item


def derive_product_scoring_evidence(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Derive ScoringEvidence v1 rows from cleaner/enrichment-owned fields.

    This adapter is the compatibility bridge for existing enriched artifacts.
    Future enrichment runs stamp these rows into product_scoring_evidence, but
    v3/v4 scoring still consume them through get_scoring_ingredients().
    """
    product = product or {}
    evidence: List[Dict[str, Any]] = []
    ptype = _primary_type(product)
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    active_rows = [row for row in _safe_list(product.get("activeIngredients")) if isinstance(row, dict)]
    skipped_rows = [row for row in _safe_list(iqd.get("ingredients_skipped")) if isinstance(row, dict)]
    scorable_paths = {
        str(row.get("raw_source_path"))
        for row in _safe_list(iqd.get("ingredients_scorable"))
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

    candidate_rows = skipped_rows + active_rows
    for parent in skipped_rows:
        parent_path = str(parent.get("raw_source_path") or "")
        if not parent_path or parent_path in scorable_paths or parent_path in special_evidence_paths:
            continue
        item = _derive_blend_header_anchor_from_nested_child(product, parent, candidate_rows)
        if item:
            special_evidence_paths.add(parent_path)
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
    product_evidence_linked_paths = {
        str(path)
        for evidence_row in product_evidence_rows
        for path in _safe_list(evidence_row.get("linked_rows"))
        if str(path)
    }
    skipped_candidates = []
    for row in _safe_list(iqd.get("ingredients_skipped")):
        if not isinstance(row, dict):
            continue
        anchor_canonical, _ = _anchor_identity(row)
        if not anchor_canonical:
            continue
        path = str(row.get("raw_source_path") or "")
        if path and path in product_evidence_linked_paths:
            continue
        role = _norm(row.get("cleaner_row_role"))
        classification = _norm(row.get("role_classification"))
        if (
            row.get("score_eligible_by_cleaner") is True
            and role == "active_scorable"
            and classification in {"active_scorable", "recognized_non_scorable", "inactive_non_scorable"}
        ):
            skipped_candidates.append(row)
            continue
        if role == "nested_display_only" and _recoverable_nested_identity(row):
            skipped_candidates.append(row)
    if skipped_candidates:
        seen_paths = {str(row.get("raw_source_path") or "") for row in candidates}
        for row in skipped_candidates:
            path = str(row.get("raw_source_path") or "")
            if path and path in seen_paths:
                continue
            recovered = dict(row)
            recovered["cleaner_row_role"] = "active_scorable"
            recovered["role_classification"] = "active_scorable"
            recovered["score_eligible_by_cleaner"] = True
            recovered["mapped"] = True
            recovered["mapped_identity"] = True
            recovered["scoreable_identity"] = True
            recovered["is_blend_header"] = False
            recovered["blend_total_weight_only"] = False
            recovered["is_proprietary_blend"] = False
            recovered["scoring_input_kind"] = "recovered_active_identity"
            recovered["scoring_input_recovery_reason"] = "mapped_active_identity_without_disclosed_dose"
            candidates.append(recovered)
            if path:
                seen_paths.add(path)
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
# Scoring Classification v1 — single route/profile seam
#
# Compatibility mode derives the contract from the current enriched blob. Native
# enrichment will call the same public builder and persist the result. Scoring
# modules should consume this contract rather than reinterpreting raw taxonomy,
# product-title regexes, or reference-file membership independently.
# ---------------------------------------------------------------------------

_CLASSIFICATION_BOTANICAL_SOURCE_FORM_CATEGORIES = {"botanical", "herb"}
_CLASSIFICATION_BOTANICAL_RAW_CATEGORIES = {"botanical", "herb"}
_CLASSIFICATION_BOTANICAL_SOURCE_TERMS = {
    "extract", "standardized", "standardised", "root", "leaf", "leaves",
    "bark", "flower", "seed", "fruit", "berry", "rhizome", "aerial",
    "whole herb", "herb", "plant part",
}
_CLASSIFICATION_DOMAIN_BY_CANONICAL = {
    "epa": "omega_epa_dha",
    "dha": "omega_epa_dha",
    "epa_dha": "omega_epa_dha",
    "fish_oil": "omega_parent",
    "fish_liver_oil": "omega_parent",
    "cod_liver_oil": "omega_parent",
    "krill_oil": "omega_parent",
    "algal_oil": "omega_parent",
    "algae_oil": "omega_parent",
    "omega_3": "omega_parent",
    "omega3": "omega_parent",
    "omega_3_fatty_acids": "fatty_acid",
    "ala": "fatty_acid",
    "alpha_linolenic_acid": "fatty_acid",
    "alpha_linolenic_acid_ala": "fatty_acid",
    "gla": "fatty_acid",
    "gamma_linolenic_acid": "fatty_acid",
    "cla": "fatty_acid",
    "conjugated_linoleic_acid": "fatty_acid",
    "oleic_acid": "fatty_acid",
    "protein": "sports_active",
    "whey_protein": "sports_active",
    "casein": "sports_active",
    "pea_protein": "sports_active",
    "rice_protein": "sports_active",
    "soy_protein": "sports_active",
    "creatine_monohydrate": "sports_active",
    "beta-alanine": "sports_active",
    "beta_alanine": "sports_active",
    "l_citrulline": "sports_active",
    "hmb": "sports_active",
    "collagen": "collagen",
    "collagen_peptides": "collagen",
    "hydrolyzed_collagen": "collagen",
    "undenatured_type_ii_collagen": "collagen",
    "digestive_enzymes": "enzyme",
}
_CLASSIFICATION_RAW_CATEGORY_DOMAINS = {
    "vitamin": "vitamin",
    "vitamins": "vitamin",
    "mineral": "mineral",
    "minerals": "mineral",
    "amino acid": "amino_acid",
    "amino_acids": "amino_acid",
    "fat": "fatty_acid",
    "fatty acid": "fatty_acid",
    "fatty_acids": "fatty_acid",
    "omega fatty acids": "fatty_acid",
    "omega_fatty_acids": "fatty_acid",
    "enzyme": "enzyme",
    "enzymes": "enzyme",
    "botanical": "herb",
    "herb": "herb",
    "probiotic": "probiotic_strain",
}
_CLASSIFICATION_VITAMIN_CANONICAL_RE = re.compile(r"^(vitamin_|folate$|choline$)")
_CLASSIFICATION_MINERAL_CANONICALS = {
    "calcium", "magnesium", "zinc", "iron", "iodine", "selenium", "manganese",
    "copper", "chromium", "molybdenum", "potassium", "sodium", "chloride",
}
_CLASSIFICATION_AMINO_CANONICAL_RE = re.compile(r"^(l_|n_acetyl|n-acetyl|amino_)")
_CLASSIFICATION_COLLAGEN_TEXT_RE = re.compile(r"\b(collagen|uc-?ii|gelatin)\b", re.IGNORECASE)
_CLASSIFICATION_PROBIOTIC_TEXT_RE = re.compile(
    r"\b(probiotic|lactobacillus|bifidobacterium|saccharomyces|bacillus|acidophilus|bifidus|cfu)\b",
    re.IGNORECASE,
)
_ROUTE_PRENATAL_KEYWORDS = re.compile(
    r"\b(prenatal|pregnancy|pre-natal|expecting|maternal|gestation)\b",
    re.IGNORECASE,
)
_ROUTE_PROBIOTIC_NAME_RE = re.compile(r"\b(probiotic|probiotics|synbiotic|synbiotics)\b", re.IGNORECASE)
_ROUTE_PROBIOTIC_ADJUNCT_PANEL_MAX = 2
_ROUTE_PROBIOTIC_HIGH_CFU_BILLIONS = 1.0
_ROUTE_PROBIOTIC_PURE_STRAIN_MIN = 2
_ROUTE_PROBIOTIC_VAGUE_TAXONOMY = frozenset({"", "general_supplement", "probiotic"})
_ROUTE_NON_PROBIOTIC_HERO_TITLE_RE = re.compile(
    r"\b(zinc|magnesium|calcium|iron|potassium|selenium|copper|chromium|iodine|"
    r"vitamin|biotin|folate|folic|niacin|thiamine|riboflavin|"
    r"protein|whey|casein|collagen|gelatin|"
    r"fiber|fibre|prebiotic|psyllium|inulin|"
    r"omega|fish\s*oil|krill|cod\s*liver|epa|dha|"
    r"quercetin|curcumin|turmeric|creatine|coq10|ubiquinol|melatonin|ashwagandha)\b",
    re.IGNORECASE,
)
_ROUTE_SPORTS_PREWORKOUT_RE = re.compile(r"\b(pre[\s-]?workout|preworkout)\b", re.IGNORECASE)
_ROUTE_SPORTS_PROTEIN_NAME_RE = re.compile(
    r"\b("
    r"whey|casein|"
    r"protein\s+(?:powder|isolate|concentrate|hydrolysate|hydrolyzed|blend|matrix)|"
    r"mass\s+gainer|gainer"
    r")\b",
    re.IGNORECASE,
)
_ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE = re.compile(
    r"\b(creatine|beta[\s-]?alanine|citrulline|hmb|bcaa|eaa|essential amino|branched chain)\b",
    re.IGNORECASE,
)
_ROUTE_SPORTS_NAME_EXCLUSION_RE = re.compile(
    r"\b(nac|n-acetyl|theanine|tryptophan|5-htp|sam-e|sleep|calm|mood|stress|"
    r"digestive|enzyme|enzymes|keratin|lactoferrin|collagen)\b",
    re.IGNORECASE,
)
_ROUTE_OMEGA_NAME_KEYWORDS = (
    "fish oil",
    "omega-3",
    "omega 3",
    "omega3",
    "krill",
    "algae oil",
    "algal oil",
    "cod liver",
    "epa+dha",
    "epa dha",
    "epa/dha",
)
_ROUTE_OMEGA_STRONG_OIL_NAME_KEYWORDS = (
    "fish oil",
    "krill",
    "algae oil",
    "algal oil",
    "cod liver",
    "epa+dha",
    "epa dha",
    "epa/dha",
)
_ROUTE_OMEGA_STANDALONE_RE = re.compile(r"\b(EPA|DHA)\b", re.IGNORECASE)
_ROUTE_OMEGA_369_RE = re.compile(r"\bomega[\s-]*3[\s-]*[-/]?[\s-]*6[\s-]*[-/]?[\s-]*9\b", re.IGNORECASE)
_ROUTE_OMEGA_EFA_RE = re.compile(r"\bEFA(?:s)?\b", re.IGNORECASE)
_ROUTE_OMEGA_INGREDIENT_CANONICALS = {"epa", "dha", "epa_dha"}
_ROUTE_B_VITAMIN_CANONICALS = {
    "vitamin_b1_thiamine",
    "vitamin_b2_riboflavin",
    "vitamin_b3_niacin",
    "vitamin_b5_pantothenic_acid",
    "vitamin_b6_pyridoxine",
    "vitamin_b7_biotin",
    "vitamin_b9_folate",
    "vitamin_b12_cobalamin",
}
_ROUTE_MULTI_PANEL_CANONICALS = _ROUTE_B_VITAMIN_CANONICALS | {
    "vitamin_a",
    "vitamin_c",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "vitamin_k1",
    "vitamin_k2",
    "folate",
    "iron",
    "iodine",
    "choline",
    "zinc",
    "magnesium",
    "calcium",
    "selenium",
    "manganese",
    "copper",
    "chromium",
    "molybdenum",
}
_ROUTE_PRENATAL_PANEL_ANCHORS = {"folate", "vitamin_b9_folate", "iron", "iodine", "choline", "dha", "epa_dha"}
_ROUTE_NON_EPA_DHA_FATTY_ACID_CANONICALS = {
    "ala",
    "alpha_linolenic_acid",
    "alpha_linolenic_acid_ala",
    "omega_3_fatty_acids",
    "gla",
    "gamma_linolenic_acid",
    "cla",
    "conjugated_linoleic_acid",
    "oleic_acid",
}
_ROUTE_OMEGA_PARENT_CANONICALS = {"fish_oil", "krill_oil", "cod_liver_oil", "algal_oil", "algae_oil", "omega_3"}
_ROUTE_SPORTS_PROTEIN_CANONICALS = {
    "whey_protein",
    "casein",
    "pea_protein",
    "rice_protein",
    "soy_protein",
}
_ROUTE_SPORTS_SINGLE_CANONICALS = {
    "creatine_monohydrate",
    "beta-alanine",
    "beta_alanine",
    "l_citrulline",
    "hmb",
}
_ROUTE_BCAA_CANONICALS = {"l_leucine", "l_isoleucine", "l_valine"}
_ROUTE_EAA_CANONICALS = {
    "l_histidine",
    "l_isoleucine",
    "l_leucine",
    "l_lysine",
    "l_methionine",
    "l_phenylalanine",
    "l_threonine",
    "l_tryptophan",
    "l_valine",
}
_ROUTE_TAXONOMY_TO_MODULE = {
    "probiotic": "probiotic",
    "multivitamin": "multi_or_prenatal",
    "b_complex": "multi_or_prenatal",
    "omega_3": "omega",
    "single_vitamin": "generic",
    "single_mineral": "generic",
    "vitamin_mineral_combo": "generic",
    "herbal_botanical": "generic",
    "protein_powder": "generic",
    "collagen": "generic",
    "greens_powder": "generic",
    "electrolyte": "generic",
    "pre_workout": "generic",
    "amino_acid": "generic",
    "fiber_digestive": "generic",
    "sleep_support": "generic",
    "immune_support": "generic",
    "joint_support": "generic",
    "beauty_hair_skin_nails": "generic",
    "general_supplement": "generic",
}


def _valid_classification_origin(origin: Any) -> str:
    origin_norm = _norm(origin) or "compatibility_derived"
    return origin_norm if origin_norm in SCORING_CLASSIFICATION_ORIGINS else "compatibility_derived"


def _route_scoring_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return [
            row for row in get_scoring_ingredients(product or {}, strict=True).rows
            if isinstance(row, dict)
        ]
    except Exception:
        return []


def _route_name_text(product: Dict[str, Any]) -> str:
    return " ".join(
        str((product or {}).get(k) or "")
        for k in ("product_name", "fullName", "brand_name", "bundleName")
    )


def _route_product_label_text(product: Dict[str, Any]) -> str:
    return " ".join(str((product or {}).get(k) or "") for k in ("product_name", "fullName"))


def _route_has_positive_quantity(row: Dict[str, Any]) -> bool:
    return _positive_quantity(row) is not None


def _route_positive_number(value: Any) -> bool:
    try:
        return value is not None and float(value) > 0
    except (TypeError, ValueError):
        return False


def _route_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _route_positive_canonicals(product: Dict[str, Any]) -> set[str]:
    canonicals: set[str] = set()
    for row in _route_scoring_rows(product):
        if row.get("scoring_input_kind") == "product_level_evidence":
            continue
        canonical = _norm(row.get("canonical_id"))
        if canonical and _route_has_positive_quantity(row):
            canonicals.add(canonical)
    return canonicals


def _route_omega_panel_counts(product: Dict[str, Any]) -> tuple[int, int]:
    omega_rows = 0
    total_rows = 0
    for row in _route_scoring_rows(product):
        if (
            row.get("scoring_input_kind") == "product_level_evidence"
            and _norm(row.get("evidence_type")) != "omega_epa_dha_aggregate"
        ):
            continue
        canonical = _norm(row.get("canonical_id"))
        if not canonical or not _route_has_positive_quantity(row):
            continue
        total_rows += 1
        if canonical in _ROUTE_OMEGA_INGREDIENT_CANONICALS:
            omega_rows += 1
    return omega_rows, total_rows


def _route_has_primary_omega_panel(product: Dict[str, Any]) -> bool:
    omega_rows, total_rows = _route_omega_panel_counts(product)
    if omega_rows <= 0 or total_rows <= 0:
        return False
    return omega_rows == total_rows or (omega_rows / total_rows) >= 0.5


def _route_has_any_epa_dha_row(product: Dict[str, Any]) -> bool:
    for row in _route_scoring_rows(product):
        canonical = _norm(row.get("canonical_id"))
        if canonical in _ROUTE_OMEGA_INGREDIENT_CANONICALS and _route_has_positive_quantity(row):
            return True
    return False


def _route_has_omega_scoring_evidence(product: Dict[str, Any]) -> bool:
    for row in _route_scoring_rows(product):
        if _norm(row.get("evidence_type")) == "omega_epa_dha_aggregate":
            return True
    return False


def _route_has_non_omega_product_level_evidence(product: Dict[str, Any]) -> bool:
    for row in _route_scoring_rows(product):
        if row.get("scoring_input_kind") != "product_level_evidence":
            continue
        evidence_type = _norm(row.get("evidence_type"))
        canonical = _norm(row.get("canonical_id"))
        if evidence_type == "omega_epa_dha_aggregate":
            continue
        if canonical in _ROUTE_OMEGA_INGREDIENT_CANONICALS or canonical in _ROUTE_OMEGA_PARENT_CANONICALS:
            continue
        return True
    return False


def _route_has_non_epa_dha_fatty_acid_panel(product: Dict[str, Any]) -> bool:
    if _route_has_any_epa_dha_row(product):
        return False
    for row in _route_scoring_rows(product):
        if _norm(row.get("canonical_id")) in _ROUTE_NON_EPA_DHA_FATTY_ACID_CANONICALS:
            return True
    return False


def _route_has_non_omega_positive_scorable_panel(product: Dict[str, Any]) -> bool:
    for row in _route_scoring_rows(product):
        if row.get("scoring_input_kind") == "product_level_evidence":
            continue
        canonical = _norm(row.get("canonical_id"))
        if not canonical or not _route_has_positive_quantity(row):
            continue
        if canonical in _ROUTE_OMEGA_INGREDIENT_CANONICALS or canonical in _ROUTE_OMEGA_PARENT_CANONICALS:
            continue
        if canonical in _ROUTE_NON_EPA_DHA_FATTY_ACID_CANONICALS:
            continue
        return True
    return False


def _route_probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    payload = (product or {}).get("probiotic_data") or (product or {}).get("probiotic_detail") or {}
    return payload if isinstance(payload, dict) else {}


def _route_non_probiotic_scorable_count(product: Dict[str, Any]) -> int:
    iqd = _safe_dict((product or {}).get("ingredient_quality_data"))
    rows = _safe_list(iqd.get("ingredients_scorable") or iqd.get("ingredients"))
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        taxonomy = _safe_dict(row.get("raw_taxonomy"))
        category = _norm(taxonomy.get("category") or row.get("category"))
        if category == "probiotic":
            continue
        count += 1
    return count


def _route_has_non_probiotic_hero(product: Dict[str, Any], name_text: str) -> bool:
    primary_type = _primary_type(product)
    if primary_type and primary_type not in _ROUTE_PROBIOTIC_VAGUE_TAXONOMY:
        return True
    return bool(_ROUTE_NON_PROBIOTIC_HERO_TITLE_RE.search(name_text or ""))


def _route_is_probiotic_class(product: Dict[str, Any], name_text: str) -> bool:
    data = _route_probiotic_payload(product)
    if not data:
        return False

    is_product = bool(data.get("is_probiotic_product") or data.get("is_probiotic"))
    strain_count = int(data.get("total_strain_count") or 0)
    has_cfu = (
        bool(data.get("has_cfu"))
        or _route_positive_number(data.get("total_cfu"))
        or _route_positive_number(data.get("total_billion_count"))
    )
    total_billion = _route_number(data.get("total_billion_count"))
    total_cfu = _route_number(data.get("total_cfu"))
    high_cfu = (
        total_billion >= _ROUTE_PROBIOTIC_HIGH_CFU_BILLIONS
        or total_cfu >= (_ROUTE_PROBIOTIC_HIGH_CFU_BILLIONS * 1_000_000_000)
    )
    name_signal = bool(_ROUTE_PROBIOTIC_NAME_RE.search(name_text or ""))

    if not is_product or strain_count <= 0:
        return False

    non_probiotic_panel = _route_non_probiotic_scorable_count(product)
    if (
        non_probiotic_panel == 0
        and strain_count >= _ROUTE_PROBIOTIC_PURE_STRAIN_MIN
        and not _route_has_non_probiotic_hero(product, name_text)
    ):
        return True

    if not (has_cfu or name_signal):
        return False

    primary_type = _primary_type(product)
    if primary_type and primary_type not in _ROUTE_PROBIOTIC_VAGUE_TAXONOMY and not name_signal:
        if not (high_cfu and non_probiotic_panel <= _ROUTE_PROBIOTIC_ADJUNCT_PANEL_MAX):
            return False

    if strain_count >= non_probiotic_panel:
        return True
    if non_probiotic_panel <= _ROUTE_PROBIOTIC_ADJUNCT_PANEL_MAX and name_signal:
        return True
    return False


def _route_is_omega_class(product: Dict[str, Any], name_text: str) -> bool:
    if _route_has_primary_omega_panel(product):
        return True
    if _ROUTE_OMEGA_369_RE.search(name_text or "") and not _route_has_any_epa_dha_row(product):
        return False
    if _ROUTE_OMEGA_EFA_RE.search(name_text or ""):
        return _route_has_any_epa_dha_row(product) or _route_has_omega_scoring_evidence(product)
    if _route_has_non_epa_dha_fatty_acid_panel(product):
        return False

    lowered = (name_text or "").lower()
    if any(token in lowered for token in _ROUTE_OMEGA_STRONG_OIL_NAME_KEYWORDS):
        if _ROUTE_OMEGA_STANDALONE_RE.search(name_text or ""):
            return True
        if _route_has_omega_scoring_evidence(product):
            return True
        if _primary_type(product) == "omega_3":
            return True
        if _route_has_non_omega_product_level_evidence(product):
            return False
        return not _route_has_non_omega_positive_scorable_panel(product)
    if any(token in lowered for token in _ROUTE_OMEGA_NAME_KEYWORDS):
        if _route_has_omega_scoring_evidence(product):
            return True
        if _ROUTE_OMEGA_STANDALONE_RE.search(name_text or ""):
            return True
        return _primary_type(product) == "omega_3"
    if _route_has_omega_scoring_evidence(product):
        return True
    return bool(_ROUTE_OMEGA_STANDALONE_RE.search(name_text or ""))


def _route_is_b_complex_eligible(product: Dict[str, Any], name_text: str) -> bool:
    lowered = (name_text or "").lower()
    if "b-complex" in lowered or "b complex" in lowered:
        return True

    b_vitamins: set[str] = set()
    non_b_scorable = 0
    for row in _route_scoring_rows(product):
        canonical = _norm(row.get("canonical_id"))
        if not canonical:
            continue
        if canonical in _ROUTE_B_VITAMIN_CANONICALS:
            b_vitamins.add(canonical)
        else:
            non_b_scorable += 1
    return len(b_vitamins) >= 4 and len(b_vitamins) > non_b_scorable


def _route_has_broad_prenatal_multi_panel(product: Dict[str, Any]) -> bool:
    canonicals = _route_positive_canonicals(product)
    multi_nutrients = canonicals & _ROUTE_MULTI_PANEL_CANONICALS
    prenatal_anchors = canonicals & _ROUTE_PRENATAL_PANEL_ANCHORS
    return len(multi_nutrients) >= 5 and len(prenatal_anchors) >= 2


def _route_is_prenatal_multi_intent(product: Dict[str, Any], name_text: str) -> bool:
    if not _ROUTE_PRENATAL_KEYWORDS.search(_route_product_label_text(product)):
        return False
    primary_type = _primary_type(product)
    if primary_type == "multivitamin":
        return True
    if primary_type == "b_complex":
        return _route_is_b_complex_eligible(product, name_text)
    return _route_has_broad_prenatal_multi_panel(product)


def _route_has_sports_primary_dose_evidence(product: Dict[str, Any]) -> bool:
    for row in _route_scoring_rows(product):
        if row.get("scoring_input_kind") != "product_level_evidence":
            continue
        if _norm(row.get("evidence_type")) != "sports_primary_dose":
            continue
        if _route_has_positive_quantity(row):
            return True
    return False


def _route_is_sports_class(product: Dict[str, Any], name_text: str) -> bool:
    primary_type = _primary_type(product)
    if _ROUTE_SPORTS_PREWORKOUT_RE.search(name_text or ""):
        return True
    if primary_type == "pre_workout":
        return True
    if _route_has_sports_primary_dose_evidence(product):
        return True

    canonicals = _route_positive_canonicals(product)
    if canonicals & _ROUTE_SPORTS_PROTEIN_CANONICALS:
        return primary_type == "protein_powder" or bool(_ROUTE_SPORTS_PROTEIN_NAME_RE.search(name_text or ""))
    if primary_type == "protein_powder" and _ROUTE_SPORTS_PROTEIN_NAME_RE.search(name_text or ""):
        return True
    if _ROUTE_BCAA_CANONICALS.issubset(canonicals) and (
        primary_type in {"amino_acid", "pre_workout"} or _ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE.search(name_text or "")
    ):
        return True
    if len(canonicals & _ROUTE_EAA_CANONICALS) >= 6 and (
        primary_type in {"amino_acid", "pre_workout"} or _ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE.search(name_text or "")
    ):
        return True
    if canonicals & _ROUTE_SPORTS_SINGLE_CANONICALS:
        if _ROUTE_SPORTS_NAME_EXCLUSION_RE.search(name_text or ""):
            return False
        return bool(_ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE.search(name_text or ""))
    return False


def _classify_route_module(product: Dict[str, Any]) -> tuple[str, str, List[str]]:
    """Independent ScoringClassification v1 route decision.

    This mirrors the current v4 route semantics so migration can prove parity,
    but lives in the classification contract. The legacy router remains only as
    an audit comparison target.
    """
    primary_type = _primary_type(product)
    name_text = _route_name_text(product)

    if primary_type == "probiotic" or (
        primary_type != "greens_powder" and _route_is_probiotic_class(product, name_text)
    ):
        return "probiotic", "profile_content:probiotic", ["probiotic_identity_or_cfu"]

    if _ROUTE_PRENATAL_KEYWORDS.search(_route_product_label_text(product)):
        if _route_has_primary_omega_panel(product):
            return "omega", "prenatal_title_with_primary_omega_panel", ["prenatal_title", "primary_omega_panel"]
        if _route_is_prenatal_multi_intent(product, name_text):
            return "multi_or_prenatal", "prenatal_multi_intent", ["prenatal_title", "multi_panel_or_taxonomy"]

    if _route_is_sports_class(product, name_text):
        return "sports", "profile_content:sports", ["sports_identity_or_dose"]

    if primary_type:
        module = _ROUTE_TAXONOMY_TO_MODULE.get(primary_type)
        if module == "multi_or_prenatal":
            if primary_type == "b_complex" and not _route_is_b_complex_eligible(product, name_text):
                return "generic", "b_complex_taxonomy_without_route_eligible_panel", ["taxonomy:b_complex"]
            return "multi_or_prenatal", f"taxonomy:{primary_type}", [f"taxonomy:{primary_type}"]
        if module == "omega":
            if _route_is_omega_class(product, name_text):
                return "omega", f"taxonomy:{primary_type}:omega_validated", [f"taxonomy:{primary_type}", "omega_evidence"]
            return "generic", f"taxonomy:{primary_type}:omega_evidence_missing", [f"taxonomy:{primary_type}"]
        if module == "sports":
            if _route_is_sports_class(product, name_text):
                return "sports", f"taxonomy:{primary_type}:sports_validated", [f"taxonomy:{primary_type}", "sports_evidence"]
            return "generic", f"taxonomy:{primary_type}:sports_evidence_missing", [f"taxonomy:{primary_type}"]
        if module == "generic":
            if _route_is_omega_class(product, name_text):
                return "omega", f"taxonomy:{primary_type}:omega_evidence_override", [f"taxonomy:{primary_type}", "omega_evidence"]
            return "generic", f"taxonomy:{primary_type}", [f"taxonomy:{primary_type}"]

    if _route_is_omega_class(product, name_text):
        return "omega", "profile_content:omega", ["omega_evidence"]
    return "generic", "generic_safe_default", ["generic_safe_default"]


def _classification_identity(row: Dict[str, Any]) -> str:
    return _slug(row.get("canonical_id") or row.get("evidence_canonical_id") or row.get("name"))


def _classification_row_text(row: Dict[str, Any]) -> str:
    pieces = [
        row.get("name"),
        row.get("standardName"),
        row.get("standard_name"),
        row.get("canonical_id"),
        row.get("raw_source_text"),
        row.get("category"),
        row.get("matched_form"),
        row.get("canonical_source_db"),
    ]
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    pieces.extend([raw_taxonomy.get("category"), raw_taxonomy.get("ingredientGroup")])
    for form in _safe_list(row.get("forms") or raw_taxonomy.get("forms")):
        if isinstance(form, dict):
            pieces.extend([form.get("name"), form.get("category"), form.get("ingredientGroup")])
        else:
            pieces.append(form)
    return " ".join(str(piece or "") for piece in pieces)


def _botanical_source_evidence(row: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Contextual botanical-source proof.

    A botanical reference-file hit is not proof by itself. Evidence must come
    from row/product source fields such as botanical taxonomy, botanical source
    form, plant part, extract/standardization wording, or a standardized
    botanical source database stamp.
    """
    evidence: List[str] = []
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    raw_category = _norm(raw_taxonomy.get("category") or row.get("category"))
    if raw_category in _CLASSIFICATION_BOTANICAL_RAW_CATEGORIES:
        evidence.append("raw_taxonomy_botanical")
    if _norm(row.get("canonical_source_db")) == "standardized_botanicals":
        evidence.append("standardized_botanical_source_db")
    for form in _safe_list(row.get("forms") or raw_taxonomy.get("forms")):
        if not isinstance(form, dict):
            continue
        if _norm(form.get("category")) in _CLASSIFICATION_BOTANICAL_SOURCE_FORM_CATEGORIES:
            evidence.append("botanical_source_form")
            break
    text = _classification_row_text(row).lower()
    if any(term in text for term in _CLASSIFICATION_BOTANICAL_SOURCE_TERMS):
        evidence.append("botanical_source_text")
    return bool(evidence), sorted(set(evidence))


def _ingredient_domain(row: Dict[str, Any], *, botanical_source: bool) -> str:
    canonical = _classification_identity(row)
    dose_class = _norm(row.get("dose_class"))
    unit = _norm(row.get("unit") or row.get("dose_unit"))
    text = _classification_row_text(row)
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    raw_category = _norm(raw_taxonomy.get("category") or row.get("category")).replace("-", "_")

    if dose_class == "probiotic_cfu" or "cfu" in unit or _CLASSIFICATION_PROBIOTIC_TEXT_RE.search(text):
        return "probiotic_strain"
    if dose_class == "enzyme_activity":
        return "enzyme"
    if canonical in _CLASSIFICATION_DOMAIN_BY_CANONICAL:
        return _CLASSIFICATION_DOMAIN_BY_CANONICAL[canonical]
    if canonical in _CLASSIFICATION_MINERAL_CANONICALS:
        return "mineral"
    if _CLASSIFICATION_VITAMIN_CANONICAL_RE.search(canonical):
        return "vitamin"
    if _CLASSIFICATION_AMINO_CANONICAL_RE.search(canonical):
        return "amino_acid"
    if _CLASSIFICATION_COLLAGEN_TEXT_RE.search(text):
        return "collagen"
    if raw_category in _CLASSIFICATION_RAW_CATEGORY_DOMAINS:
        return _CLASSIFICATION_RAW_CATEGORY_DOMAINS[raw_category]
    if botanical_source:
        return "herb"
    if canonical:
        return "generic_active"
    return "unknown"


def _profile_eligibility_for_row(
    row: Dict[str, Any],
    *,
    domain: str,
    botanical_source: bool,
    botanical_evidence: List[str],
) -> Dict[str, Dict[str, Any]]:
    canonical = _classification_identity(row)
    positive_dose = _positive_quantity(row) is not None
    evidence_type = _norm(row.get("evidence_type"))
    profile: Dict[str, Dict[str, Any]] = {
        "botanical": {
            "eligible": bool(botanical_source and domain in {"herb", "botanical_marker", "generic_active"}),
            "reason": "positive_botanical_source_evidence" if botanical_source else "no_botanical_source_evidence",
            "evidence": botanical_evidence,
        },
        "omega": {
            "eligible": domain in {"omega_epa_dha", "omega_parent"} or evidence_type == "omega_epa_dha_aggregate",
            "reason": "omega_identity_or_aggregate_evidence" if domain in {"omega_epa_dha", "omega_parent"} or evidence_type == "omega_epa_dha_aggregate" else "not_omega_identity",
            "evidence": [canonical] if canonical else [],
        },
        "probiotic": {
            "eligible": domain == "probiotic_strain",
            "reason": "probiotic_identity_or_cfu" if domain == "probiotic_strain" else "not_probiotic_identity",
            "evidence": [canonical] if canonical else [],
        },
        "sports": {
            "eligible": domain == "sports_active" or evidence_type == "sports_primary_dose",
            "reason": "sports_primary_identity_or_dose" if domain == "sports_active" or evidence_type == "sports_primary_dose" else "not_sports_identity",
            "evidence": [canonical] if canonical else [],
        },
        "collagen": {
            "eligible": domain == "collagen",
            "reason": "collagen_identity" if domain == "collagen" else "not_collagen_identity",
            "evidence": [canonical] if canonical else [],
        },
    }
    if positive_dose:
        for payload in profile.values():
            if payload["eligible"]:
                payload.setdefault("evidence", []).append("positive_dose")
    return profile


def _route_confidence(
    route_module: str,
    rows: List[Dict[str, Any]],
    *,
    failed: bool,
    forced_generic_reason: Optional[str],
) -> str:
    if failed:
        return "failed"
    if forced_generic_reason:
        return "low"
    if route_module != "generic":
        return "high"
    if rows:
        return "medium"
    return "low"


def _product_profile_summary(row_contracts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for profile_name in ("botanical", "omega", "probiotic", "sports", "collagen"):
        eligible_rows = [
            row for row in row_contracts
            if _safe_dict(_safe_dict(row.get("profile_eligibility")).get(profile_name)).get("eligible") is True
        ]
        summary[profile_name] = {
            "eligible": bool(eligible_rows),
            "eligible_row_count": len(eligible_rows),
            "evidence": sorted({
                str(e)
                for row in eligible_rows
                for e in _safe_list(_safe_dict(_safe_dict(row.get("profile_eligibility")).get(profile_name)).get("evidence"))
                if str(e)
            }),
        }
    return summary


def build_scoring_classification(
    product: Dict[str, Any],
    *,
    route_module: Optional[str] = None,
    classification_origin: str = "compatibility_derived",
) -> Dict[str, Any]:
    """Build ScoringClassification v1 for a product.

    Total function: never raises, always returns a schema-valid dict. In
    compatibility mode the route is derived from the current enriched blob by
    this contract. The legacy router is kept as an audit-only parity target.
    """
    product = product if isinstance(product, dict) else {}
    origin = _valid_classification_origin(classification_origin)
    failed = False
    failure_reason: Optional[str] = None
    route_reason = ""
    route_evidence: List[str] = []
    rows: List[Dict[str, Any]] = []
    roles: List[Dict[str, Any]] = []

    try:
        input_result = get_scoring_ingredients(product, strict=True)
        rows = list(input_result.rows)
    except Exception as exc:  # pragma: no cover - defensive totality path
        failed = True
        failure_reason = f"scoring_input_failed:{exc.__class__.__name__}"
        rows = []

    if route_module not in SCORING_ROUTE_MODULES:
        try:
            route_module, route_reason, route_evidence = _classify_route_module(product)
        except Exception as exc:  # pragma: no cover
            failed = True
            failure_reason = failure_reason or f"route_failed:{exc.__class__.__name__}"
            route_module = "generic"
            route_reason = failure_reason
            route_evidence = ["route_classification_failed"]
    else:
        route_reason = f"explicit_route:{route_module}"
        route_evidence = [route_module]
    if route_module not in SCORING_ROUTE_MODULES:
        route_module = "generic"
        if not route_reason:
            route_reason = "invalid_route_generic_fallback"
        if not route_evidence:
            route_evidence = ["invalid_route_generic_fallback"]

    if rows:
        try:
            roles = classify_ingredient_roles(product, module=route_module, rows=rows)
        except Exception as exc:  # pragma: no cover - role failure is debt, not crash
            failed = True
            failure_reason = failure_reason or f"role_classification_failed:{exc.__class__.__name__}"
            roles = []

    role_by_key: Dict[str, Dict[str, Any]] = {}
    for role in roles:
        if not isinstance(role, dict):
            continue
        for key in (_slug(role.get("canonical_id")), _slug(role.get("name"))):
            if key:
                role_by_key.setdefault(key, role)

    row_contracts: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        botanical_source, botanical_evidence = _botanical_source_evidence(row)
        domain = _ingredient_domain(row, botanical_source=botanical_source)
        role = role_by_key.get(_classification_identity(row)) or role_by_key.get(_slug(row.get("name"))) or {}
        row_contracts.append({
            "row_index": index,
            "row_ref": row.get("raw_source_path") or row.get("source") or f"scoring_row:{index}",
            "canonical_id": row.get("canonical_id") or row.get("evidence_canonical_id"),
            "name": row.get("name") or row.get("standardName") or row.get("raw_source_text"),
            "ingredient_domain": domain,
            "botanical_source": {
                "value": botanical_source,
                "evidence": botanical_evidence,
            },
            "role": role.get("role") or ROLE_ADJUNCT,
            "role_reason": role.get("role_reason") or "classification_default",
            "role_source": role.get("role_source") or "classification_default",
            "role_confidence": role.get("role_confidence") or ("low" if failed else "medium"),
            "profile_eligibility": _profile_eligibility_for_row(
                row,
                domain=domain,
                botanical_source=botanical_source,
                botanical_evidence=botanical_evidence,
            ),
            "confidence": "low" if failed or domain == "unknown" else "medium",
        })

    forced_generic_reason = None
    if failed:
        route_module = "generic"
        forced_generic_reason = failure_reason or "classification_failed"

    confidence = _route_confidence(
        route_module,
        rows,
        failed=failed,
        forced_generic_reason=forced_generic_reason,
    )
    route_evidence = list(route_evidence or [route_module])
    if rows:
        route_evidence.append("scoring_rows_present")
    if forced_generic_reason:
        route_evidence.append(forced_generic_reason)

    return {
        "classification_schema_version": SCORING_CLASSIFICATION_SCHEMA_VERSION,
        "classification_origin": origin,
        "classification_failed": failed,
        "classification_failure_reason": failure_reason,
        "route_module": route_module,
        "route_reason": forced_generic_reason or route_reason or f"classification_route:{route_module}",
        "route_confidence": confidence,
        "route_evidence": route_evidence,
        "ingredients": row_contracts,
        "profile_eligibility": _product_profile_summary(row_contracts),
    }


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

# Title surfaces that imply a canonical ingredient even when the row's current
# display name is broader. Example: labels often say "tocotrienols" while the
# enriched row is canonicalized to vitamin_e / Vitamin E; the role classifier
# still needs to know the product title is selling that row.
_ROLE_TITLE_ALIASES_BY_CANONICAL = {
    "vitamin_e": ("tocotrienol", "tocotrienols", "tocopherol", "tocopherols"),
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
    """Module driver canonical IDs from the scoring classification contract."""
    if module == "omega":
        # EPA/DHA AND the fish-oil/krill/algal parents that route a product to
        # the omega module — a parent-only row is still the module driver. (WR-01)
        return set(_ROUTE_OMEGA_INGREDIENT_CANONICALS) | set(_ROUTE_OMEGA_PARENT_CANONICALS)
    if module == "sports":
        return (
            set(_ROUTE_SPORTS_PROTEIN_CANONICALS)
            | set(_ROUTE_SPORTS_SINGLE_CANONICALS)
            | set(_ROUTE_BCAA_CANONICALS)
            | set(_ROUTE_EAA_CANONICALS)
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
    canonical = _norm(row.get("canonical_id"))
    candidates = [
        _norm(row.get("name")),
        _norm(row.get("standardName")),
        _norm(row.get("standard_name")),
        canonical.replace("_", " "),
    ]
    candidates.extend(_ROLE_TITLE_ALIASES_BY_CANONICAL.get(canonical, ()))
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
    rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Classify every scoring row's role (compatibility mode, Phase 2).

    Returns one provenance dict per row in
    ``get_scoring_ingredients(product).rows`` order. CLASSIFY ONLY — changes no
    score, cap, or verdict. When ``module`` is omitted it is resolved via the
    router (``class_for_product``).

    ``rows`` lets a caller that has already derived the scoring rows (e.g. the
    completeness gate) pass them in to avoid a second derivation pass. When
    omitted they are derived from ``product``.
    """
    product = product or {}
    if rows is None:
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
