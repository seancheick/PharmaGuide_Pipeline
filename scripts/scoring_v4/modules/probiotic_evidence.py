"""v4 Probiotic Evidence dimension — P2.3.

The probiotic Evidence rubric has two lines:

  - strain-clinical evidence pipeline: 12
  - indication relevance to product positioning: 8

The first line reuses the already-verified v4 multiplicative evidence
pipeline and caps its contribution at 12 for the probiotic module. The
second line is deliberately conservative and based only on available
label/product text plus enriched clinical-strain indication text. It
does not invent condition matching when the source fields are absent.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set

from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence


PHASE_MARKER = "P2.3_probiotic_evidence"
CAP_EVIDENCE = 20.0
CAP_STRAIN_CLINICAL = 12.0
CAP_INDICATION_RELEVANCE = 8.0

INDICATION_KEYWORDS: Dict[str, Set[str]] = {
    "digestive": {
        "digestive", "digestion", "gut", "bowel", "regularity", "constipation",
        "diarrhea", "ibs", "irritable", "bloating", "gastro", "colic",
    },
    "immune": {
        "immune", "immunity", "respiratory", "cold", "allergy", "allergic",
        "rhinitis", "eczema", "atopic",
    },
    "women": {
        "women", "woman", "womens", "female", "vaginal", "urogenital",
        "vaginosis", "bv", "urinary", "uti",
    },
    "prenatal": {
        "prenatal", "pregnancy", "pregnant", "maternal", "postnatal",
        "postpartum",
    },
    "infant": {
        "infant", "baby", "pediatric", "children", "child", "kids",
        "toddler", "preterm", "neonatal",
    },
    "oral": {"oral", "dental", "teeth", "gum", "gingivitis", "plaque", "caries", "halitosis"},
    "metabolic": {"weight", "metabolic", "glucose", "glycemic", "visceral", "fat"},
    "mood": {"mood", "stress", "anxiety", "cognition", "psychobiotic", "sleep"},
    "bone": {"bone", "density"},
}

BROAD_PROBIOTIC_CATEGORIES = {"digestive", "immune"}
PARTIAL_RELEVANCE_PAIRS = {
    ("prenatal", "infant"),
    ("prenatal", "immune"),
    ("women", "prenatal"),
    ("digestive", "immune"),
}

EFFECT_DIRECTION_MULTIPLIERS = {
    "positive_strong": 1.0,
    "positive_weak": 0.85,
    "mixed": 0.6,
    "null": 0.25,
    "negative": 0.0,
}


def score_evidence(product: Any) -> Dict[str, Any]:
    """Return the probiotic Evidence dimension payload."""
    product = product if isinstance(product, dict) else {}

    generic_payload = score_generic_evidence(product)
    generic_score = _as_float(generic_payload.get("score"), 0.0)
    strain_clinical = min(CAP_STRAIN_CLINICAL, generic_score)

    relevance = _score_indication_relevance(product)
    indication_relevance = relevance["score"]

    components = {
        "strain_clinical_evidence": round(strain_clinical, 4),
        "indication_relevance": round(indication_relevance, 4),
    }
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_EVIDENCE, raw_score))

    return {
        "score": round(score, 4),
        "max": CAP_EVIDENCE,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "generic_evidence_score": generic_score,
            "generic_evidence_metadata": generic_payload.get("metadata", {}),
            "clinical_strain_count": len(_clinical_strains(product)),
            "indication_relevance_level": relevance["level"],
            "product_positioning_categories": sorted(relevance["product_categories"]),
            "strain_indication_categories": sorted(relevance["strain_categories"]),
            "matched_relevance_categories": sorted(relevance["matched_categories"]),
            "relevance_reason": relevance["reason"],
            "indication_effect_multiplier": relevance["effect_multiplier"],
        },
    }


def _score_indication_relevance(product: Dict[str, Any]) -> Dict[str, Any]:
    product_categories = _product_positioning_categories(product)
    strain_categories = _strain_indication_categories(product)
    matched = product_categories & strain_categories
    effect_multiplier = _best_effect_direction_multiplier(product)

    if matched:
        return _relevance(
            8.0 * effect_multiplier,
            "direct",
            product_categories,
            strain_categories,
            matched,
            "direct_category_overlap",
            effect_multiplier,
        )

    partial = {
        b
        for a, b in PARTIAL_RELEVANCE_PAIRS
        if (a in product_categories and b in strain_categories)
        or (b in product_categories and a in strain_categories)
    }
    if partial:
        return _relevance(
            4.0 * effect_multiplier,
            "partial",
            product_categories,
            strain_categories,
            partial,
            "related_category_overlap",
            effect_multiplier,
        )

    if not product_categories and (strain_categories & BROAD_PROBIOTIC_CATEGORIES):
        broad = strain_categories & BROAD_PROBIOTIC_CATEGORIES
        return _relevance(
            4.0 * effect_multiplier,
            "broad",
            product_categories,
            strain_categories,
            broad,
            "generic_probiotic_positioning",
            effect_multiplier,
        )

    if not product_categories and not strain_categories:
        return _relevance(
            0.0,
            "not_evaluable",
            product_categories,
            strain_categories,
            set(),
            "missing_positioning_or_indication_data",
            effect_multiplier,
        )

    return _relevance(
        0.0,
        "none",
        product_categories,
        strain_categories,
        set(),
        "no_relevance_overlap",
        effect_multiplier,
    )


def _relevance(
    score: float,
    level: str,
    product_categories: Set[str],
    strain_categories: Set[str],
    matched_categories: Set[str],
    reason: str,
    effect_multiplier: float,
) -> Dict[str, Any]:
    return {
        "score": min(CAP_INDICATION_RELEVANCE, score),
        "level": level,
        "product_categories": product_categories,
        "strain_categories": strain_categories,
        "matched_categories": matched_categories,
        "reason": reason,
        "effect_multiplier": effect_multiplier,
    }


def _best_effect_direction_multiplier(product: Dict[str, Any]) -> float:
    matches = _safe_list(_safe_dict(product.get("evidence_data")).get("clinical_matches"))
    if not matches:
        return 1.0
    best = 0.0
    for match in matches:
        if not isinstance(match, dict):
            continue
        effect = _norm_text(match.get("effect_direction") or "positive_strong").replace(" ", "_")
        best = max(best, EFFECT_DIRECTION_MULTIPLIERS.get(effect, 1.0))
    return best


def _product_positioning_categories(product: Dict[str, Any]) -> Set[str]:
    text = " ".join(
        str(product.get(field) or "")
        for field in ("product_name", "brand_name", "serving_description", "suggested_use")
    )
    categories = _categories_from_text(text)
    # "Probiotic" by itself is generic class text, not a targeted claim.
    categories.discard("probiotic")
    return categories


def _strain_indication_categories(product: Dict[str, Any]) -> Set[str]:
    categories: Set[str] = set()
    for strain in _clinical_strains(product):
        text_parts = [
            strain.get("indication_primary"),
            strain.get("indication_secondary"),
            strain.get("clinical_support_level"),
        ]
        categories.update(_categories_from_text(" ".join(str(x or "") for x in text_parts)))
    return categories


def _clinical_strains(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    pdata = _probiotic_payload(product)
    return [row for row in _safe_list(pdata.get("clinical_strains")) if isinstance(row, dict)]


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))


def _categories_from_text(text: str) -> Set[str]:
    normalized = _norm_text(text)
    if not normalized:
        return set()
    categories: Set[str] = set()
    words = set(normalized.split())
    for category, keywords in INDICATION_KEYWORDS.items():
        if words & keywords:
            categories.add(category)
    return categories


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


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
