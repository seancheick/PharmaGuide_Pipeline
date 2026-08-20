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


ROUTE_FEATURE_SCHEMA_VERSION = "1.0.0"

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
    r"\b(fib(?:er|re)|psyllium|inulin|prebiotic|glucomannan|guar|"
    r"wheat\s+dextrin|resistant\s+starch|bran)\b",
    re.IGNORECASE,
)
_DIGESTIVE_TITLE_RE = re.compile(
    r"\b(digestive|digestion|digest|gut\s+health|enzyme\s+digestion)\b",
    re.IGNORECASE,
)
_B_COMPLEX_TITLE_RE = re.compile(r"\bb[\s-]*complex\b", re.IGNORECASE)
_MULTIVITAMIN_TITLE_RE = re.compile(
    r"\b(multi[\s-]*vitamin|multi[\s-]*mineral)\b",
    re.IGNORECASE,
)
_PROTEIN_TITLE_RE = re.compile(
    r"\b(?:"
    r"protein|whey|casein|"
    r"mass[\s-]*gainer|weight[\s-]*gainer"
    r")\b",
    re.IGNORECASE,
)

_PRIMARY_ROLES = frozenset({"primary", "claim_prominent"})
_MATERIAL_ROLES = frozenset({"primary", "claim_prominent", "major"})


def normalize_identity(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def product_label_text(product: Mapping[str, Any]) -> str:
    return " ".join(
        str(product.get(field) or "")
        for field in ("product_name", "fullName", "name", "bundleName")
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
    label_rows = [row for row in positive_rows if not _is_product_level_evidence(row)]
    mass_rows = [row for row in label_rows if _mass_owner_row(row)]
    canonical_ids = sorted({row_canonical(row) for row in label_rows if row_canonical(row)})

    fiber_rows = [row for row in label_rows if row_canonical(row) in FIBER_CANONICALS]
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
    ]
    systemic_enzyme_rows = [
        row for row in enzyme_rows
        if row_canonical(row) in SYSTEMIC_ENZYME_CANONICALS
    ]
    protein_rows = [row for row in label_rows if row_canonical(row) in PROTEIN_CANONICALS]

    observed_fiber_rows = [
        row for row in observed_row_list
        if row_canonical(row) in FIBER_CANONICALS
    ]
    observed_digestive_enzyme_rows = [
        row for row in observed_row_list
        if row_canonical(row) in DIGESTIVE_ENZYME_CANONICALS
    ]
    observed_dual_use_enzyme_rows = [
        row for row in observed_row_list
        if row_canonical(row) in DUAL_USE_ENZYME_CANONICALS
    ]
    observed_systemic_enzyme_rows = [
        row for row in observed_row_list
        if row_canonical(row) in SYSTEMIC_ENZYME_CANONICALS
    ]
    observed_nutrition_fiber_rows = [
        row for row in observed_fiber_rows
        if str(row.get("score_exclusion_reason") or "").strip().lower()
        == "excluded_nutrition_fact"
    ]

    total_mass = sum(comparable_mass_mg(row) or 0.0 for row in mass_rows)
    fiber_mass = sum(comparable_mass_mg(row) or 0.0 for row in fiber_rows if _mass_owner_row(row))
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
    non_b_vitamin_ids = sorted(set(canonical_ids) & NON_B_VITAMIN_CANONICALS)
    adek_ids = sorted(set(canonical_ids) & ADEK_VITAMIN_CANONICALS)
    mineral_ids = sorted(set(canonical_ids) & MINERAL_CANONICALS)
    panel_identity_count = len(set(canonical_ids))

    route_module = str((classification or {}).get("route_module") or "").strip().lower() or None
    title_fiber_intent = bool(_FIBER_TITLE_RE.search(label_text))
    title_digestive_intent = bool(_DIGESTIVE_TITLE_RE.search(label_text))
    title_b_complex_intent = bool(_B_COMPLEX_TITLE_RE.search(label_text))
    title_multivitamin_intent = bool(_MULTIVITAMIN_TITLE_RE.search(label_text))

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
        "panel_identity_count": panel_identity_count,
        "comparable_active_mass_mg": _rounded(total_mass),
        "title_fiber_intent": title_fiber_intent,
        "title_digestive_intent": title_digestive_intent,
        "taxonomy_fiber_digestive": primary_type in {"fiber_digestive", "digestive_enzyme"},
        "fiber_canonical_ids": sorted({row_canonical(row) for row in fiber_rows}),
        "fiber_row_count": len(fiber_rows),
        "fiber_mass_mg": _rounded(fiber_mass),
        "fiber_mass_share": _rounded(fiber_mass / total_mass) if total_mass > 0 and fiber_mass > 0 else None,
        "fiber_primary_role": bool(fiber_roles & _PRIMARY_ROLES),
        "fiber_material_role": bool(fiber_roles & _MATERIAL_ROLES),
        "observed_fiber_row_count": len(observed_fiber_rows),
        "observed_nutrition_fiber_row_count": len(observed_nutrition_fiber_rows),
        "enzyme_canonical_ids": sorted({row_canonical(row) for row in enzyme_rows}),
        "digestive_enzyme_row_count": len(digestive_enzyme_rows),
        "systemic_enzyme_row_count": len(systemic_enzyme_rows),
        "systemic_enzyme_only": bool(systemic_enzyme_rows and not digestive_enzyme_rows),
        "observed_digestive_enzyme_row_count": len(observed_digestive_enzyme_rows),
        "observed_dual_use_enzyme_row_count": len(observed_dual_use_enzyme_rows),
        "observed_systemic_enzyme_row_count": len(observed_systemic_enzyme_rows),
        "digestive_enzyme_context": bool(
            title_digestive_intent
            or observed_digestive_enzyme_rows
        ),
        "title_b_complex_intent": title_b_complex_intent,
        "title_multivitamin_intent": title_multivitamin_intent,
        "b_vitamin_ids": b_ids,
        "b_vitamin_count": len(b_ids),
        "non_b_vitamin_ids": non_b_vitamin_ids,
        "non_b_vitamin_count": len(non_b_vitamin_ids),
        "ade_k_vitamin_ids": adek_ids,
        "ade_k_vitamin_count": len(adek_ids),
        "mineral_ids": mineral_ids,
        "mineral_count": len(mineral_ids),
        "b_panel_identity_share": _rounded(len(b_ids) / panel_identity_count) if panel_identity_count else None,
        "protein_canonical_ids": sorted({row_canonical(row) for row in protein_rows}),
        "protein_row_count": len(protein_rows),
        "protein_mass_mg": _rounded(protein_mass),
        "protein_title_intent": has_protein_product_intent(label_text),
        "protein_primary_role": bool(protein_roles & _PRIMARY_ROLES),
        "protein_material_role": bool(protein_roles & _MATERIAL_ROLES),
    }
