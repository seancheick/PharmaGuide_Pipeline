from __future__ import annotations

from typing import Any


PROBIOTIC_TERMS = (
    "probiotic",
    "lactobacillus",
    "bifidobacterium",
    "streptococcus",
    "bacillus",
    "saccharomyces",
    "limosilactobacillus",
    "lacticaseibacillus",
)

NON_SCORABLE_CATEGORIES = {
    "excipient",
    "additive",
    "inactive",
    "blend_header",
    "non_therapeutic",
}

CATEGORY_ALIASES = {
    "vitamin": "vitamin",
    "vitamins": "vitamin",
    "mineral": "mineral",
    "minerals": "mineral",
    "herb": "herb",
    "herbs": "herb",
    "botanical": "botanical",
    "botanicals": "botanical",
    "probiotic": "probiotic",
    "probiotics": "probiotic",
    "bacteria": "bacteria",
    "protein": "protein",
    "proteins": "protein",
    "fiber": "fiber",
    "fibers": "fiber",
    "fatty acid": "fatty_acid",
    "fatty acids": "fatty_acid",
    "fatty_acid": "fatty_acid",
    "fatty_acids": "fatty_acid",
    "amino acid": "amino_acid",
    "amino acids": "amino_acid",
    "amino_acid": "amino_acid",
    "amino_acids": "amino_acid",
    "enzyme": "enzyme",
    "enzymes": "enzyme",
    "antioxidant": "antioxidant",
    "antioxidants": "antioxidant",
    "functional food": "functional_food",
    "functional foods": "functional_food",
    "functional_food": "functional_food",
    "functional_foods": "functional_food",
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def canonical_category(value: Any) -> str:
    normalized = _normalize_text(value).replace("-", "_").replace(" ", "_")
    if not normalized:
        return ""
    return CATEGORY_ALIASES.get(normalized, normalized)


def _ingredient_name(row: dict[str, Any]) -> str:
    return _normalize_text(
        row.get("standard_name")
        or row.get("standardName")
        or row.get("name")
        or row.get("raw_source_text")
    )


def _iter_classification_rows(product: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    iqd_rows = _safe_list(product.get("ingredient_quality_data", {}).get("ingredients"))
    if iqd_rows:
        return [row for row in iqd_rows if isinstance(row, dict)], "ingredient_quality_data"

    active_rows = _safe_list(product.get("activeIngredients"))
    return [row for row in active_rows if isinstance(row, dict)], "activeIngredients"


def infer_supplement_type(product: dict[str, Any]) -> dict[str, Any]:
    rows, source = _iter_classification_rows(product)
    inactive_count = len(_safe_list(product.get("inactiveIngredients")))

    scorable_rows: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    probiotic_name_count = 0

    for row in rows:
        category = canonical_category(row.get("category"))
        role = _normalize_text(row.get("role_classification"))
        if category in NON_SCORABLE_CATEGORIES:
            continue
        if role in {"recognized_non_scorable", "inactive_non_scorable"}:
            continue
        if bool(row.get("is_proprietary_blend")):
            continue
        if bool(row.get("is_blend_header")) or bool(row.get("blend_total_weight_only")):
            continue

        name = _ingredient_name(row)
        if not name and not category:
            continue

        scorable_rows.append(row)
        counted_category = category or "uncategorized"
        category_counts[counted_category] = category_counts.get(counted_category, 0) + 1

        if category not in {"probiotic", "bacteria"} and any(term in name for term in PROBIOTIC_TERMS):
            probiotic_name_count += 1

    active_count = len(scorable_rows)
    raw_active_count = len(_safe_list(product.get("activeIngredients"))) or len(rows)
    total_count = raw_active_count + inactive_count

    product_name_text = _normalize_text(
        " ".join(
            str(product.get(key) or "")
            for key in ("product_name", "fullName", "bundleName")
        )
    )
    probiotic_name_signal = any(term in product_name_text for term in PROBIOTIC_TERMS)
    probiotic_flag = bool(product.get("probiotic_data", {}).get("is_probiotic_product"))
    probiotic_total = (
        category_counts.get("probiotic", 0)
        + category_counts.get("bacteria", 0)
        + probiotic_name_count
    )

    supplement_type = "unknown"
    if probiotic_flag and active_count > 0 and (
        active_count == 1
        or probiotic_total >= max(1, active_count * 0.5)
        or (probiotic_name_signal and probiotic_total >= 1)
    ):
        supplement_type = "probiotic"
    elif active_count == 1:
        supplement_type = "single_nutrient"
    elif category_counts.get("botanical", 0) + category_counts.get("herb", 0) > active_count * 0.6:
        supplement_type = "herbal_blend"
    elif active_count >= 6 and len([key for key in category_counts if key != "uncategorized"]) >= 3:
        supplement_type = "multivitamin"
    elif 2 <= active_count <= 5:
        categorized_keys = [key for key in category_counts if key != "uncategorized"]
        if len(categorized_keys) <= 2:
            supplement_type = "targeted"
        else:
            supplement_type = "specialty"
    elif active_count > 0:
        supplement_type = "specialty"

    return {
        "type": supplement_type,
        "active_count": active_count,
        "raw_active_count": raw_active_count,
        "total_count": total_count,
        "category_breakdown": category_counts,
        "source": source,
        "probiotic_signal": probiotic_flag,
    }
