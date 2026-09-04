"""Probiotic evidence: research support /12 and reviewed dose applicability /8.

Claim wording is descriptive only. Unknown-dose strain presence is contextual
research, capped at the strongest single native record; it cannot accumulate
full evidence credit by adding more strains. Formula evidence owns its scope.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
from scoring_v4.modules.generic_evidence import resolved_clinical_matches
from studied_formulas import (assess_studied_formula, assess_probiotic_evidence,
                             independent_clinical_strains, strain_assessments_for_match)


PHASE_MARKER = "P2.3_probiotic_evidence"
from scoring_v4.quality_score_config import block as _cfg_block

_EM = _cfg_block("evidence_magnitudes", "probiotic")["probiotic"]


CAP_EVIDENCE = _EM["cap_evidence"]
CAP_STRAIN_CLINICAL = _EM["cap_strain_clinical"]
CAP_DOSE_APPLICABILITY = _EM["cap_dose_applicability"]

INDICATION_KEYWORDS: Dict[str, Set[str]] = {
    "digestive": {
        "digestive", "digestion", "gut", "bowel", "regularity", "constipation",
        "diarrhea", "ibs", "irritable", "bloating", "gastro", "colic", "gi",
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

POSITIONING_STATEMENT_TYPES = {
    "general statements all other content",
    "formula re type",
    "formulation re other",
}

BROAD_PROBIOTIC_CATEGORIES = {"digestive", "immune"}
PARTIAL_RELEVANCE_PAIRS = {
    ("prenatal", "infant"),
    ("prenatal", "immune"),
    ("women", "prenatal"),
    ("digestive", "immune"),
}

EFFECT_DIRECTION_MULTIPLIERS = dict(_EM["effect_direction_multipliers"])

NATIVE_STRAIN_EVIDENCE_POINTS = dict(_EM["native_strain_evidence_points"])

NATIVE_STRAIN_EVIDENCE_WEIGHTS = tuple(_EM["native_strain_evidence_weights"])


def score_evidence(product: Any) -> Dict[str, Any]:
    """Return the probiotic Evidence dimension payload."""
    product = product if isinstance(product, dict) else {}

    assessment = assess_probiotic_evidence(product)
    matches, _ = resolved_clinical_matches(product)
    accepted = [m for m in matches if not _is_strain_match(m)
                or strain_assessments_for_match(m, assessment)]
    generic_payload = score_generic_evidence(product, accepted_matches=accepted)
    generic_score = _as_float(generic_payload.get("score"), 0.0)
    native_evidence = _score_native_clinical_strain_evidence(
        matches=accepted,
        assessment=assessment,
    )
    strain_clinical = min(
        CAP_STRAIN_CLINICAL,
        max(generic_score, native_evidence["score"]),
    )

    relevance = _claim_alignment(product)
    # Claim alignment is descriptive only. Native dose applicability must be
    # reviewed; generic 1B/10B/50B bands and marketing phrases cannot prove it.
    formula = assessment["formula_assessment"]
    applicable_effects = [_effect_multiplier(m) for m in accepted
                         if m.get("id") == formula.get("evidence_id")
                         and formula["status"] == "assessed_studied_formula"]
    applicable_effects += [r["effect_multiplier"] for r in native_evidence["rows"] if r["dose_applicable"]]
    applicability_credit = CAP_DOSE_APPLICABILITY * max(applicable_effects, default=0.0)
    if not applicable_effects:
        strain_clinical = min(strain_clinical, max(NATIVE_STRAIN_EVIDENCE_POINTS.values()))

    components = {
        "strain_clinical_evidence": round(strain_clinical, 4),
        "dose_applicability": round(applicability_credit, 4),
    }
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_EVIDENCE, raw_score))
    if score == 0 and any(_norm_text(m.get("effect_direction")) == "negative" for m in accepted):
        evidence_state = "evaluated_unfavorable"
    elif applicable_effects:
        evidence_state = "evaluated_applicable"
    elif score > 0:
        evidence_state = "research_present_applicability_unestablished"
    else:
        evidence_state = "applicability_unestablished"

    return {
        "score": round(score, 4),
        "max": CAP_EVIDENCE,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "evidence_assessment": assessment,
            "evidence_result_state": evidence_state,
            "claim_alignment": relevance,
            "studied_formula_assessment": formula,
            "uncredited_strain_match_ids": [m.get("id") for m in matches if m not in accepted],
            "generic_evidence_score": generic_score,
            "generic_evidence_metadata": generic_payload.get("metadata", {}),
            "native_clinical_strain_evidence_score": round(native_evidence["score"], 4),
            "native_clinical_strain_evidence_rows": native_evidence["rows"],
            "clinical_strain_count": len(_clinical_strains(product)),
            "indication_relevance_level": relevance["level"],
            "product_positioning_categories": sorted(relevance["product_categories"]),
            "strain_indication_categories": sorted(relevance["strain_categories"]),
            "matched_relevance_categories": sorted(relevance["matched_categories"]),
            "relevance_reason": relevance["reason"],
        },
    }


def _score_native_clinical_strain_evidence(
    *,
    matches: list,
    assessment: dict,
) -> Dict[str, Any]:
    """Score probiotic-native clinical strain evidence already found by enrichment.

    The generic evidence pipeline remains the preferred evidence source when it
    matches. This fallback prevents a second-brain gap where
    ``probiotic_data.clinical_strains`` identifies a known clinical strain but
    ``evidence_data.clinical_matches`` is empty, which otherwise produces zero
    strain evidence for products like BB536-only probiotics.
    """

    seen: Set[str] = set()
    rows: List[Dict[str, Any]] = []
    for strain in assessment["strain_assessments"]:
        if not strain["research_accepted"] or strain["status"] in {
            "strain_dose_incompatible", "strain_context_mismatch", "strain_context_unresolved"
        }:
            continue
        key = _native_strain_key(strain)
        if key in seen:
            continue
        seen.add(key)

        support_token = _norm_text(strain["support_level"])
        base_points = NATIVE_STRAIN_EVIDENCE_POINTS.get(support_token, 0.0)
        if base_points <= 0:
            continue

        rows.append(
            {
                "clinical_id": strain.get("clinical_id"),
                "strain": (
                    strain.get("strain")
                    or strain.get("standard_name")
                    or strain.get("name")
                ),
                "support_level": support_token,
                "base_points": base_points,
                "dose_applicable": strain["dose_applicable"],
                "applicability_status": strain["status"],
                "source_pmids": strain["source_pmids"],
                "evidence_scope": strain["evidence_scope"],
                "effect_multiplier": min((_effect_multiplier(m) for m in matches
                    if strain in strain_assessments_for_match(m, assessment)), default=1.0),
            }
        )

    rows.sort(key=lambda row: (-row["base_points"] * row["effect_multiplier"], str(row["clinical_id"])))
    # Undosed strain presence is contextual research, not cumulative proof for
    # a blend. Keep the strongest such record; stack only dose-applicable rows.
    contextual = [r for r in rows if not r["dose_applicable"]][:1]
    applicable = [r for r in rows if r["dose_applicable"]]
    rows = applicable or contextual
    weighted_score = 0.0
    weighted_rows: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows[: len(NATIVE_STRAIN_EVIDENCE_WEIGHTS)]):
        weight = NATIVE_STRAIN_EVIDENCE_WEIGHTS[idx]
        contribution = row["base_points"] * weight * row["effect_multiplier"]
        weighted_score += contribution
        weighted_rows.append(
            {
                **row,
                "weight": weight,
                "contribution": round(contribution, 4),
            }
        )

    return {
        "score": min(CAP_STRAIN_CLINICAL, weighted_score),
        "rows": weighted_rows,
    }


def _claim_alignment(product: Dict[str, Any]) -> Dict[str, Any]:
    product_categories = _product_positioning_categories(product)
    strain_categories = _strain_indication_categories(product)
    matched = product_categories & strain_categories
    partial = {
        b
        for a, b in PARTIAL_RELEVANCE_PAIRS
        if (a in product_categories and b in strain_categories)
        or (b in product_categories and a in strain_categories)
    }
    broad = strain_categories & BROAD_PROBIOTIC_CATEGORIES
    if matched:
        level, reason = "direct", "direct_category_overlap"
    elif partial:
        level, reason, matched = "partial", "related_category_overlap", partial
    elif not product_categories and broad:
        level, reason, matched = "broad", "generic_probiotic_positioning", broad
    elif not product_categories and not strain_categories:
        level, reason = "not_evaluable", "missing_positioning_or_indication_data"
    else:
        level, reason = "none", "no_relevance_overlap"
    return {
        "level": level,
        "product_categories": sorted(product_categories),
        "strain_categories": sorted(strain_categories),
        "matched_categories": sorted(matched),
        "reason": reason,
    }


def _is_strain_match(match: dict) -> bool:
    return (match.get("study_type") == "clinical_strain"
            or str(match.get("evidence_level", "")).replace("_", "-") == "strain-clinical")


def _effect_multiplier(match: dict) -> float:
    effect = _norm_text(match.get("effect_direction") or "positive_strong").replace(" ", "_")
    return EFFECT_DIRECTION_MULTIPLIERS.get(effect, 0.0)


def _product_positioning_categories(product: Dict[str, Any]) -> Set[str]:
    text_parts = [
        str(product.get(field) or "")
        for field in ("product_name", "brand_name", "serving_description", "suggested_use")
    ]
    for statement in _safe_list(product.get("statements")):
        if not isinstance(statement, dict):
            continue
        statement_type = _norm_text(statement.get("type"))
        if statement_type not in POSITIONING_STATEMENT_TYPES:
            continue
        text_parts.append(str(statement.get("notes") or statement.get("text") or ""))
    categories = _categories_from_text(" ".join(text_parts))
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
    formula = assess_studied_formula(product)
    if formula["status"] == "assessed_studied_formula":
        categories.update(formula["supported_outcomes"])
    return categories


def _clinical_strains(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return independent_clinical_strains(product)


def _native_strain_key(strain: Dict[str, Any]) -> str:
    return _norm_text(
        strain.get("clinical_id")
        or strain.get("canonical_id")
        or strain.get("strain")
        or strain.get("standard_name")
        or strain.get("name")
    )


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
