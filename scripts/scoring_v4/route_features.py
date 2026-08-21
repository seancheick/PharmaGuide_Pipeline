"""Pure feature extraction for the canonical v4 route decision.

This module does not choose a route and does not read pipeline files.  It turns
an enriched product plus its already-selected strict scoring rows into one
typed, reproducible feature record.  Both the production router and shadow
audits can therefore inspect the same label facts without duplicating identity,
mass, or title predicates.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence


ROUTE_FEATURE_SCHEMA_VERSION = "1.1.0"

B_VITAMIN_CANONICALS = frozenset({
    "vitamin_b1_thiamine",
    "vitamin_b2_riboflavin",
    "vitamin_b3_niacin",
    "vitamin_b5_pantothenic_acid",
    "vitamin_b5_pantothenic",
    "vitamin_b6_pyridoxine",
    "vitamin_b7_biotin",
    "vitamin_b9_folate",
    "vitamin_b12_cobalamin",
    "folate",
})

B_COFACTOR_CANONICALS = frozenset({
    "choline",
    "inositol",
    "paba",
})

NON_B_VITAMIN_CANONICALS = frozenset({
    "vitamin_a",
    "vitamin_c",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "vitamin_k1",
    "vitamin_k2",
})

ADEK_VITAMIN_CANONICALS = frozenset({
    "vitamin_a",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "vitamin_k1",
    "vitamin_k2",
})

MINERAL_CANONICALS = frozenset({
    "iron",
    "iodine",
    "zinc",
    "magnesium",
    "calcium",
    "selenium",
    "manganese",
    "copper",
    "chromium",
    "molybdenum",
})

FIBER_CANONICALS = frozenset({
    "fiber",
    "psyllium",
    "psyllium_husk",
    "inulin",
    "acacia_fiber",
    "acacia_gum",
    "partially_hydrolyzed_guar_gum",
    "guar_gum",
    "glucomannan",
    "konjac_glucomannan",
    "beta_glucan",
    "wheat_dextrin",
    "pectin",
    "resistant_starch",
    "prebiotics",
})

# These identities can define a fiber product when they dominate disclosed
# comparable active mass.  Generic prebiotic and beta-glucan rows need explicit
# label intent because they are frequently adjuncts in probiotic/immune formulas.
MATERIAL_FIBER_CANONICALS = FIBER_CANONICALS - {"prebiotics", "beta_glucan"}

DIGESTIVE_ENZYME_CANONICALS = frozenset({
    "digestive_enzymes",
    "alpha_amylase",
    "amylase",
    "pepsin",
    "protease",
    "lipase",
    "cellulase",
    "lactase",
    "pancreatin",
})

DUAL_USE_ENZYME_CANONICALS = frozenset({
    "bromelain",
    "papain",
})

SYSTEMIC_ENZYME_CANONICALS = frozenset({
    "nattokinase",
    "serrapeptase",
    "serratiopeptidase",
    "lumbrokinase",
})

PROTEIN_CANONICALS = frozenset({
    "protein",
    "whey_protein",
    "casein",
    "pea_protein",
    "rice_protein",
    "soy_protein",
})

_FIBER_TITLE_RE = re.compile(
    r"\b(fib(?:er|re)(?:mend|con|lax)?|psyllium|inulin|prebiotic|"
    r"glucomannan|konjac|guar|pectin|wheat\s+dextrin|resistant\s+starch|bran|"
    r"colon|bowel|intestinal|regularity|regulate|g\.?\s*i\.?)\b",
    re.IGNORECASE,
)
_DIGESTIVE_TITLE_RE = re.compile(
    r"\b(digestive|digestion|digest|gut\s+health|enzymes|multi[\s-]*enzyme|"
    r"enzyme\s+(?:blend|formula)|pancrea\w*\s+enzymes?|vegenzymes?|"
    r"papaya\s+enzyme|lactase|pepsin|betaine\s+hcl|dairy\s+(?:relief|defense|digestant)|"
    r"beanaid|megazymes?|acid\s+(?:defense|ease)|heartburn|enzyme\s+digestion)\b",
    re.IGNORECASE,
)
_EXPLICIT_DIGESTIVE_CONTEXT_RE = re.compile(
    r"\b(digestive|digestion|digest|gut\s+health|lactase|pepsin|betaine\s+hcl|"
    r"pancrea\w*|dairy\s+(?:relief|defense|digestant)|beanaid|"
    r"acid\s+(?:defense|ease)|heartburn)\b",
    re.IGNORECASE,
)
_SYSTEMIC_ENZYME_TITLE_RE = re.compile(
    r"\b(systemic|nattokinase|serrapeptase|serratiopeptidase|lumbrokinase|"
    r"wobenzym|joint\s+health|inflammation)\b",
    re.IGNORECASE,
)
_B_COMPLEX_TITLE_RE = re.compile(
    r"(?:\bb[\s-]*complex\b|"
    r"\b(?:balanced\s+)?b[\s-]?(?:50|100|150)\b|"
    r"\bb[\s-]*6\s+complex\b|"
    r"\bb[\s-]*(?:right|unstressed)\b|"
    r"\bsuper\s+b\s+energy\s+complex\b)",
    re.IGNORECASE,
)
_MULTIVITAMIN_TITLE_RE = re.compile(r"\bmulti[\s-]*vitamin\b", re.IGNORECASE)
_MULTIMINERAL_TITLE_RE = re.compile(r"\bmulti[\s-]*mineral\b", re.IGNORECASE)
_PROTEIN_TITLE_RE = re.compile(
    r"\b(?:"
    r"protein|whey|casein|"
    r"mass[\s-]*gainer|weight[\s-]*gainer|gainer|mass|muscle"
    r")\b",
    re.IGNORECASE,
)
_PROBIOTIC_LABEL_RE = re.compile(
    r"\b(probiotic|probiotics|trubiotics|synbiotic|synbiotics|acidophilus|"
    r"lactobacillus|bifidobacterium|saccharomyces|bacillus)\b",
    re.IGNORECASE,
)

_PRIMARY_ROLES = frozenset({"primary", "claim_prominent"})
_MATERIAL_ROLES = frozenset({"primary", "claim_prominent", "major"})
_FIBER_CATEGORY_VALUES = frozenset({"fiber", "fibers"})
_FIBER_DECLARATION_RE = re.compile(
    r"\b(fib(?:er|re)|psyllium|inulin|prebiotic|glucomannan|guar|pectin|"
    r"wheat\s+dextrin|resistant\s+starch|bran)\b",
    re.IGNORECASE,
)
_FIBER_DELIVERY_CARRIER_RE = re.compile(r"\bgalactomannans?\b", re.IGNORECASE)
_DUAL_USE_ENZYME_NAME_RE = re.compile(r"\b(bromelain|papain)\b", re.IGNORECASE)
_SYSTEMIC_ENZYME_NAME_RE = re.compile(
    r"\b(nattokinase|serrapeptase|serratiopeptidase|lumbrokinase)\b",
    re.IGNORECASE,
)


def normalize_identity(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def product_label_text(product: Mapping[str, Any]) -> str:
    return " ".join(
        str(product.get(field) or "")
        for field in (
            "product_name",
            "fullName",
            "name",
            "bundleName",
            "brand_name",
            "brandName",
        )
    ).strip()


def has_protein_product_intent(title: Any) -> bool:
    """Return whether product-title text explicitly markets protein/sports mass.

    The predicate deliberately accepts bare ``protein`` and both source-first
    (``whey protein isolate``) and form-first (``protein isolate - whey``)
    wording.  Production routing must still pair this title fact with a material
    protein identity or product-level mass; title text alone never selects a
    specialized route.
    """
    return bool(_PROTEIN_TITLE_RE.search(str(title or "")))


def positive_number(row: Mapping[str, Any]) -> float | None:
    for field in (
        "quantity",
        "normalized_amount",
        "dosage",
        "dose_value",
        "amount",
    ):
        value = row.get(field)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _probiotic_features(
    product: Mapping[str, Any],
    label_text: str,
    primary_type: str,
) -> dict[str, Any]:
    payload = product.get("probiotic_data") or product.get("probiotic_detail") or {}
    payload = payload if isinstance(payload, Mapping) else {}
    blends = [
        row for row in payload.get("probiotic_blends") or []
        if isinstance(row, Mapping)
    ]
    named_identity_count = sum(
        1
        for row in blends
        if (row.get("strain_identity_texts") or row.get("strains"))
    )
    total_cfu = _number(payload.get("total_cfu"))
    total_billion = _number(payload.get("total_billion_count"))
    has_cfu = bool(payload.get("has_cfu")) or total_cfu > 0 or total_billion > 0
    return {
        "probiotic_label_intent": bool(_PROBIOTIC_LABEL_RE.search(label_text)),
        "probiotic_primary_type": primary_type == "probiotic",
        "probiotic_is_product": bool(
            payload.get("is_probiotic_product") or payload.get("is_probiotic")
        ),
        "probiotic_strain_count": int(payload.get("total_strain_count") or 0),
        "probiotic_named_identity_count": named_identity_count,
        "probiotic_has_cfu": has_cfu,
        "probiotic_total_cfu": total_cfu,
        "probiotic_total_billion_count": total_billion,
        "probiotic_cfu_source": str(payload.get("cfu_source") or "") or None,
        "probiotic_blend_count": len(blends),
        "probiotic_blend_names": sorted({
            str(row.get("name") or "").strip()
            for row in blends
            if str(row.get("name") or "").strip()
        }),
    }


def comparable_mass_mg(row: Mapping[str, Any]) -> float | None:
    """Return positive row mass in mg; activity/IU/CFU units are incomparable."""
    value = positive_number(row)
    if value is None:
        return None
    unit = str(
        row.get("unit_normalized")
        or row.get("unit")
        or row.get("normalized_unit")
        or row.get("dose_unit")
        or ""
    ).strip().lower().replace(" ", "")
    if unit in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return value
    if unit in {"g", "gram", "grams", "gram(s)"}:
        return value * 1000.0
    if unit in {
        "mcg",
        "ug",
        "µg",
        "μg",
        "microgram",
        "micrograms",
        "microgram(s)",
    }:
        return value / 1000.0
    return None


def row_canonical(row: Mapping[str, Any]) -> str:
    return normalize_identity(
        row.get("canonical_id")
        or row.get("evidence_canonical_id")
        or row.get("scoring_parent_id")
    )


def row_name(row: Mapping[str, Any]) -> str:
    return str(
        row.get("name")
        or row.get("standard_name")
        or row.get("standardName")
        or row.get("raw_source_text")
        or ""
    ).strip()


def row_category(row: Mapping[str, Any]) -> str:
    return normalize_identity(row.get("category")).replace("_", " ")


def is_fiber_row(row: Mapping[str, Any]) -> bool:
    """Return whether the row has a reviewed canonical fiber identity.

    The upstream ``category`` field is useful audit context but is not an
    identity contract: the live corpus also labels glucosamine, chondroitin,
    and hyaluronic acid as ``fibers``.  Category-only rows must therefore not
    contribute material fiber mass or satisfy fiber routing evidence.
    """
    return row_canonical(row) in FIBER_CANONICALS


def is_fiber_category_row(row: Mapping[str, Any]) -> bool:
    """Return the raw upstream category signal for measurement only."""
    return row_category(row) in _FIBER_CATEGORY_VALUES


def is_declared_fiber_blend(row: Mapping[str, Any]) -> bool:
    """Return whether a non-nutrition structural row declares fiber intent."""
    disposition = str(row.get("score_exclusion_reason") or "").strip().lower()
    if disposition == "excluded_nutrition_fact":
        return False
    if disposition not in {"blend_header_total", "recognized_non_scorable"}:
        return False
    return bool(_FIBER_DECLARATION_RE.search(row_name(row)))


def is_dual_use_enzyme_row(row: Mapping[str, Any]) -> bool:
    return (
        row_canonical(row) in DUAL_USE_ENZYME_CANONICALS
        or bool(_DUAL_USE_ENZYME_NAME_RE.search(row_name(row)))
    )


def is_systemic_enzyme_row(row: Mapping[str, Any]) -> bool:
    return (
        row_canonical(row) in SYSTEMIC_ENZYME_CANONICALS
        or bool(_SYSTEMIC_ENZYME_NAME_RE.search(row_name(row)))
    )


def _is_product_level_evidence(row: Mapping[str, Any]) -> bool:
    return str(row.get("scoring_input_kind") or "").strip().lower() == "product_level_evidence"


def _mass_owner_row(row: Mapping[str, Any]) -> bool:
    if _is_product_level_evidence(row):
        return False
    if row.get("is_parent_total") is True:
        return False
    if row.get("is_blend_header") is True or row.get("blend_total_weight_only") is True:
        return False
    return True


def _classification_role_maps(
    classification: Mapping[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    by_ref: dict[str, str] = {}
    by_canonical: dict[str, str] = {}
    for row in (classification or {}).get("ingredients") or []:
        if not isinstance(row, Mapping):
            continue
        role = str(row.get("role") or "").strip().lower()
        row_ref = str(row.get("row_ref") or "").strip()
        canonical = normalize_identity(row.get("canonical_id"))
        if row_ref and role:
            by_ref.setdefault(row_ref, role)
        if canonical and role:
            by_canonical.setdefault(canonical, role)
    return by_ref, by_canonical


def _row_role(
    row: Mapping[str, Any],
    by_ref: Mapping[str, str],
    by_canonical: Mapping[str, str],
) -> str:
    row_ref = str(
        row.get("raw_source_path")
        or row.get("source")
        or ""
    ).strip()
    canonical = row_canonical(row)
    return by_ref.get(row_ref) or by_canonical.get(canonical) or ""


def _rounded(value: float) -> float:
    return round(value, 6)


def extract_route_features(
    product: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    classification: Mapping[str, Any] | None = None,
    *,
    observed_rows: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one deterministic route-feature record from strict scoring rows."""
    row_list = [row for row in rows if isinstance(row, Mapping)]
    observed_row_list = (
        [row for row in observed_rows if isinstance(row, Mapping)]
        if observed_rows is not None
        else list(row_list)
    )
    label_text = product_label_text(product)
    taxonomy = product.get("supplement_taxonomy")
    taxonomy = taxonomy if isinstance(taxonomy, Mapping) else {}
    primary_type = str(taxonomy.get("primary_type") or product.get("primary_type") or "").strip().lower()
    by_ref, by_canonical = _classification_role_maps(classification)

    positive_rows = [row for row in row_list if positive_number(row) is not None]
    product_level_rows = [row for row in positive_rows if _is_product_level_evidence(row)]
    label_rows = [row for row in positive_rows if not _is_product_level_evidence(row)]
    mass_rows = [row for row in label_rows if _mass_owner_row(row)]
    canonical_ids = sorted({row_canonical(row) for row in label_rows if row_canonical(row)})

    fiber_rows = [row for row in label_rows if is_fiber_row(row)]
    fiber_category_rows = [
        row for row in label_rows
        if is_fiber_category_row(row) and not is_fiber_row(row)
    ]
    enzyme_rows = [
        row for row in label_rows
        if row_canonical(row) in (
            DIGESTIVE_ENZYME_CANONICALS
            | DUAL_USE_ENZYME_CANONICALS
            | SYSTEMIC_ENZYME_CANONICALS
        )
    ]
    digestive_enzyme_rows = [
        row for row in enzyme_rows
        if row_canonical(row) in DIGESTIVE_ENZYME_CANONICALS
        and not is_dual_use_enzyme_row(row)
        and not is_systemic_enzyme_row(row)
    ]
    systemic_enzyme_rows = [
        row for row in enzyme_rows
        if is_systemic_enzyme_row(row)
    ]
    protein_rows = [row for row in label_rows if row_canonical(row) in PROTEIN_CANONICALS]

    product_level_fiber_rows = [row for row in product_level_rows if is_fiber_row(row)]
    product_level_protein_rows = [
        row for row in product_level_rows
        if row_canonical(row) in PROTEIN_CANONICALS
    ]
    product_level_digestive_enzyme_rows = [
        row for row in product_level_rows
        if row_canonical(row) in DIGESTIVE_ENZYME_CANONICALS
        and not is_dual_use_enzyme_row(row)
        and not is_systemic_enzyme_row(row)
    ]

    observed_fiber_rows = [
        row for row in observed_row_list
        if is_fiber_row(row)
    ]
    observed_fiber_category_rows = [
        row for row in observed_row_list
        if is_fiber_category_row(row) and not is_fiber_row(row)
    ]
    observed_digestive_enzyme_rows = [
        row for row in observed_row_list
        if row_canonical(row) in DIGESTIVE_ENZYME_CANONICALS
        and not is_dual_use_enzyme_row(row)
        and not is_systemic_enzyme_row(row)
    ]
    observed_dual_use_enzyme_rows = [
        row for row in observed_row_list
        if is_dual_use_enzyme_row(row)
    ]
    observed_systemic_enzyme_rows = [
        row for row in observed_row_list
        if is_systemic_enzyme_row(row)
    ]
    observed_nutrition_fiber_rows = [
        row for row in observed_fiber_rows
        if str(row.get("score_exclusion_reason") or "").strip().lower()
        == "excluded_nutrition_fact"
    ]
    declared_fiber_blend_rows = [
        row for row in observed_row_list
        if is_declared_fiber_blend(row)
    ]

    total_mass = sum(comparable_mass_mg(row) or 0.0 for row in mass_rows)
    fiber_mass = sum(comparable_mass_mg(row) or 0.0 for row in fiber_rows if _mass_owner_row(row))
    product_level_fiber_mass = max(
        (comparable_mass_mg(row) or 0.0 for row in product_level_fiber_rows),
        default=0.0,
    )
    protein_mass_candidates = [
        comparable_mass_mg(row)
        for row in positive_rows
        if row_canonical(row) in PROTEIN_CANONICALS
    ]
    protein_mass = max((mass for mass in protein_mass_candidates if mass is not None), default=0.0)

    fiber_roles = {
        _row_role(row, by_ref, by_canonical)
        for row in fiber_rows
    }
    protein_roles = {
        _row_role(row, by_ref, by_canonical)
        for row in protein_rows
    }
    b_ids = sorted(set(canonical_ids) & B_VITAMIN_CANONICALS)
    b_cofactor_ids = sorted(set(canonical_ids) & B_COFACTOR_CANONICALS)
    non_b_vitamin_ids = sorted(set(canonical_ids) & NON_B_VITAMIN_CANONICALS)
    adek_ids = sorted(set(canonical_ids) & ADEK_VITAMIN_CANONICALS)
    mineral_ids = sorted(set(canonical_ids) & MINERAL_CANONICALS)
    panel_identity_count = len(set(canonical_ids))
    b_family_identity_count = len(set(b_ids) | set(b_cofactor_ids))

    route_module = str((classification or {}).get("route_module") or "").strip().lower() or None
    title_fiber_intent = bool(_FIBER_TITLE_RE.search(label_text))
    title_digestive_intent = bool(_DIGESTIVE_TITLE_RE.search(label_text))
    title_explicit_digestive_context = bool(
        _EXPLICIT_DIGESTIVE_CONTEXT_RE.search(label_text)
    )
    title_systemic_enzyme_intent = bool(_SYSTEMIC_ENZYME_TITLE_RE.search(label_text))
    title_b_complex_intent = bool(_B_COMPLEX_TITLE_RE.search(label_text))
    title_multivitamin_intent = bool(_MULTIVITAMIN_TITLE_RE.search(label_text))
    title_multimineral_intent = bool(_MULTIMINERAL_TITLE_RE.search(label_text))
    probiotic_features = _probiotic_features(product, label_text, primary_type)

    return {
        "feature_schema_version": ROUTE_FEATURE_SCHEMA_VERSION,
        "dsld_id": str(product.get("dsld_id") or product.get("dsldId") or product.get("id") or ""),
        "product_name": str(product.get("product_name") or product.get("fullName") or product.get("name") or ""),
        "brand_name": str(product.get("brand_name") or product.get("brandName") or ""),
        "primary_type": primary_type or None,
        "current_route": route_module,
        "route_reason": (classification or {}).get("route_reason"),
        "route_confidence": (classification or {}).get("route_confidence"),
        "canonical_ids": canonical_ids,
        "positive_label_row_count": len(label_rows),
        "product_level_evidence_row_count": len(product_level_rows),
        "panel_identity_count": panel_identity_count,
        "comparable_active_mass_mg": _rounded(total_mass),
        "title_fiber_intent": title_fiber_intent,
        "title_digestive_intent": title_digestive_intent,
        "title_explicit_digestive_context": title_explicit_digestive_context,
        "title_systemic_enzyme_intent": title_systemic_enzyme_intent,
        "taxonomy_fiber_digestive": primary_type in {"fiber_digestive", "digestive_enzyme"},
        "fiber_canonical_ids": sorted({row_canonical(row) for row in fiber_rows}),
        "fiber_row_count": len(fiber_rows),
        "fiber_category_row_count": len(fiber_category_rows),
        "fiber_mass_mg": _rounded(fiber_mass),
        "product_level_fiber_mass_mg": _rounded(product_level_fiber_mass),
        "fiber_mass_share": _rounded(fiber_mass / total_mass) if total_mass > 0 and fiber_mass > 0 else None,
        "fiber_delivery_carrier_only": bool(
            fiber_rows
            and all(_FIBER_DELIVERY_CARRIER_RE.search(row_name(row)) for row in fiber_rows)
        ),
        "fiber_primary_role": bool(fiber_roles & _PRIMARY_ROLES),
        "fiber_material_role": bool(fiber_roles & _MATERIAL_ROLES),
        "observed_fiber_row_count": len(observed_fiber_rows),
        "observed_fiber_category_row_count": len(observed_fiber_category_rows),
        "observed_nutrition_fiber_row_count": len(observed_nutrition_fiber_rows),
        "declared_fiber_blend_intent": bool(declared_fiber_blend_rows),
        "declared_fiber_blend_names": sorted({row_name(row) for row in declared_fiber_blend_rows}),
        "product_level_fiber_row_count": len(product_level_fiber_rows),
        "enzyme_canonical_ids": sorted({row_canonical(row) for row in enzyme_rows}),
        "digestive_enzyme_row_count": len(digestive_enzyme_rows),
        "systemic_enzyme_row_count": len(systemic_enzyme_rows),
        "systemic_enzyme_only": bool(systemic_enzyme_rows and not digestive_enzyme_rows),
        "observed_digestive_enzyme_row_count": len(observed_digestive_enzyme_rows),
        "observed_dual_use_enzyme_row_count": len(observed_dual_use_enzyme_rows),
        "observed_systemic_enzyme_row_count": len(observed_systemic_enzyme_rows),
        "product_level_digestive_enzyme_row_count": len(product_level_digestive_enzyme_rows),
        "digestive_enzyme_context": bool(
            title_digestive_intent
            or observed_digestive_enzyme_rows
        ),
        "title_b_complex_intent": title_b_complex_intent,
        "title_multivitamin_intent": title_multivitamin_intent,
        "title_multimineral_intent": title_multimineral_intent,
        "b_vitamin_ids": b_ids,
        "b_vitamin_count": len(b_ids),
        "b_cofactor_ids": b_cofactor_ids,
        "b_cofactor_count": len(b_cofactor_ids),
        "non_b_vitamin_ids": non_b_vitamin_ids,
        "non_b_vitamin_count": len(non_b_vitamin_ids),
        "ade_k_vitamin_ids": adek_ids,
        "ade_k_vitamin_count": len(adek_ids),
        "mineral_ids": mineral_ids,
        "mineral_count": len(mineral_ids),
        "b_panel_identity_share": _rounded(len(b_ids) / panel_identity_count) if panel_identity_count else None,
        "b_family_identity_share": _rounded(b_family_identity_count / panel_identity_count) if panel_identity_count else None,
        "protein_canonical_ids": sorted({row_canonical(row) for row in protein_rows}),
        "protein_row_count": len(protein_rows),
        "protein_mass_mg": _rounded(protein_mass),
        "product_level_protein_row_count": len(product_level_protein_rows),
        "protein_title_intent": has_protein_product_intent(label_text),
        "protein_primary_role": bool(protein_roles & _PRIMARY_ROLES),
        "protein_material_role": bool(protein_roles & _MATERIAL_ROLES),
        **probiotic_features,
    }
