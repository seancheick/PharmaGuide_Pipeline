#!/usr/bin/env python3
"""Version-neutral scoring input contract.

Scoring consumes cleaner/enrichment decisions from this module instead of
rediscovering active rows from labels or legacy raw fields.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Shared, dependency-free reference resolver (contract -> shared resolver <- scorer).
# Importing it here is safe: the resolver imports nothing from the contract or
# the scorer and only reads data files lazily.
from scoring_reference_resolver import has_therapeutic_reference, is_known_botanical

# Single source of truth for identity disposition vocabulary and scoreability.
# Never copy the disposition list here; the contract must consume the same policy
# the enricher stamps rows with.
from identity_integrity import IDENTITY_DISPOSITIONS, is_identity_scoreable


_DATA_DIR = Path(__file__).resolve().parent / "data"
_IQM_PATH = _DATA_DIR / "ingredient_quality_map.json"
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
SCORING_CLASSIFICATION_SCHEMA_VERSION = "1.1.4"
SCORING_CLASSIFICATION_ORIGINS = {"compatibility_derived", "native_enrichment"}
SCORING_ROUTE_MODULES = {"generic", "probiotic", "multi_or_prenatal", "b_complex", "omega", "sports", "fiber_digestive"}
SCORING_ROUTE_CONFIDENCE = {"high", "medium", "low", "failed"}
_ROUTE_SCORING_ROWS_CACHE_KEY = "__scoring_input_contract_route_rows_cache"
SCORING_CLASSIFICATION_REQUIRED_FIELDS = {
    "classification_schema_version",
    "classification_origin",
    "classification_failed",
    "route_module",
    "route_reason",
    "route_confidence",
    "route_evidence",
    "ingredients",
    "profile_eligibility",
}
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
_SPORTS_PRIMARY_TYPES = {"protein_powder", "sports"}
_PROTEIN_CANONICALS = {"protein", "whey_protein", "casein", "pea_protein", "rice_protein", "soy_protein"}
_CREATINE_CANONICALS = {
    "creatine",
    "creatine_monohydrate",
    "creatine_anhydrous",
    "creatine_hydrochloride",
    "creatine_hcl",
    "creatine_nitrate",
    "creatine_citrate",
    "buffered_creatine",
    "magnesium_creatine_chelate",
}
_SPORTS_PRIMARY_CANONICALS = _PROTEIN_CANONICALS | {
    *_CREATINE_CANONICALS,
    "beta-alanine",
    "beta_alanine",
    "l_citrulline",
    "hmb",
    "l_leucine",
    "l_isoleucine",
    "l_valine",
}
_PROBIOTIC_IDENTITY_RE = re.compile(
    r"\b("
    r"probiotic|lactobacillus|bifidobacterium|streptococcus|saccharomyces|"
    r"bacillus|limosilactobacillus|acidophilus|dophilus|bifidus|cfu"
    r")\b",
    re.IGNORECASE,
)
_PROBIOTIC_SUPPORT_CANONICALS = {"fiber", "prebiotics"}
_ROUTE_MULTIVITAMIN_BROAD_PANEL_MIN = 8
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
_EPA_DHA_SOURCE_RE = re.compile(
    r"\b(epa|dha|eicosapentaenoic|docosahexaenoic)\b",
    re.IGNORECASE,
)
_MARINE_OMEGA_SOURCE_RE = re.compile(
    r"\b("
    r"fish\s+oil|fish\s+body\s+oil|salmon\s+oil|anchovy\s+oil|sardine\s+oil|"
    r"mackerel\s+oil|tuna\s+oil|menhaden\s+oil|herring\s+oil|cod\s+liver|"
    r"krill|algae\s+oil|algal\s+oil|calamari\s+oil|squid\s+oil|marine\s+oil"
    r")\b",
    re.IGNORECASE,
)
_NON_EPA_DHA_SOURCE_RE = re.compile(
    r"\b("
    r"mct|medium\s+chain\s+triglycerides?|coconut|caprylic|capric|palm|"
    r"flax(?:seed)?|linseed|alpha[-\s]?linolenic|ala|chia|hemp|"
    r"evening\s+primrose|borage|gamma[-\s]?linolenic|gla|"
    r"conjugated\s+linoleic|cla|omega[-\s]?6|omega[-\s]?9|"
    r"fiber|fibre|seed\s+blend|super\s+seed"
    r")\b",
    re.IGNORECASE,
)
_ENZYME_UNITS = {
    "alu", "ppi", "blgu", "hut", "sapu", "fip", "cu", "gdu", "dppiv", "dpp-iv",
    "lacu", "fccpu", "galu", "au", "skb", "mwu", "pu", "dp", "ckpu", "aju", "usp",
    "du", "pc", "agu", "bgu", "lu", "phy", "ftu", "su",
}
_ENZYME_ACTIVITY_RE = re.compile(
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>ALU|PPI|BLGU|HUT|SAPU|FIP|CU|GDU|DPP[- ]?IV|LACU|FCCPU|GALU|AU|SKB|MWU|PU|DP|CKPU|AJU|USP|DU|PC|AGU|BGU|LU|PHY|FTU|SU)(?:\b|$)",
    re.IGNORECASE,
)
_TITLE_MASS_RE = re.compile(
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>mg|milligrams?|g|grams?|mcg|µg|μg|micrograms?)\b",
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
_BOTANICAL_BLEND_NAME_STRIP_RE = re.compile(
    r"\b("
    r"organic|wildcrafted|standardized|standardised|extract|powder|root|leaf|"
    r"leaves|seed|seeds|fruit|berry|berries|flower|bark|rhizome|aerial|"
    r"whole|herb|herbal"
    r")\b",
    re.IGNORECASE,
)
_BOTANICAL_BLEND_GENERIC_KEYS = {
    "blend",
    "complex",
    "formula",
    "matrix",
    "proprietary",
    "proprietary_blend",
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


def _row_source_text(row: Dict[str, Any]) -> str:
    """Label/source identity excluding canonicalized standard names.

    Standard names can already be polluted by a bad parent match. For example,
    current false positives contain ``name=Medium Chain Triglyceride`` while
    ``standardName`` has become DHA. Trust the label/source fields when deciding
    whether an EPA/DHA canonical is biologically plausible.
    """
    pieces = [
        row.get("name"),
        row.get("raw_source_text"),
        row.get("display_label"),
        row.get("normalized_key"),
        row.get("parent_key"),
        row.get("matched_candidate"),
    ]
    return " ".join(str(piece or "") for piece in pieces).strip()


def _source_has_epa_dha_identity(row: Dict[str, Any]) -> bool:
    return bool(_EPA_DHA_SOURCE_RE.search(_row_source_text(row)))


def _source_is_marine_omega_parent(row: Dict[str, Any]) -> bool:
    return bool(_MARINE_OMEGA_SOURCE_RE.search(_row_source_text(row)))


def _source_is_non_epa_dha_oil(row: Dict[str, Any]) -> bool:
    return bool(_NON_EPA_DHA_SOURCE_RE.search(_row_source_text(row)))


def _trustworthy_epa_dha_row(row: Dict[str, Any]) -> bool:
    canonical = _norm(row.get("canonical_id"))
    if canonical not in {"epa", "dha", "epa_dha"}:
        return False
    if _positive_quantity(row) is None:
        return False
    if not _unit_is_mass(row.get("unit") or row.get("unit_normalized") or row.get("dose_unit")):
        return False
    if _source_is_non_epa_dha_oil(row) and not _source_has_epa_dha_identity(row):
        return False
    return True


def _trustworthy_omega_parent_row(row: Dict[str, Any], canonical: str) -> bool:
    if canonical not in _OMEGA_EVIDENCE_CANONICALS:
        return False
    if _source_is_non_epa_dha_oil(row) and not _source_has_epa_dha_identity(row):
        return False
    return _source_is_marine_omega_parent(row) or _source_has_epa_dha_identity(row)


def _slug(value: Any) -> str:
    text = _norm(value)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


@lru_cache(maxsize=1)
def _botanical_identity_lookup() -> Dict[str, Dict[str, str]]:
    try:
        raw = json.loads((_DATA_DIR / "botanical_ingredients.json").read_text())
    except Exception:  # pragma: no cover - missing data only disables fallback evidence
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for entry in _safe_list(raw.get("botanical_ingredients")):
        if not isinstance(entry, dict):
            continue
        canonical = _slug(entry.get("id"))
        if not canonical:
            continue
        display = str(entry.get("standard_name") or entry.get("id") or canonical)
        keys = [
            entry.get("id"),
            entry.get("standard_name"),
            entry.get("latin_name"),
        ] + _safe_list(entry.get("aliases"))
        for key in keys:
            for variant in (_norm(key), _slug(key)):
                if variant:
                    out.setdefault(variant, {"canonical_id": canonical, "name": display})
    return out


@lru_cache(maxsize=1)
def _botanical_phrase_patterns() -> tuple[tuple[str, re.Pattern[str], Dict[str, str]], ...]:
    lookup = _botanical_identity_lookup()
    patterns: List[tuple[str, re.Pattern[str], Dict[str, str]]] = []
    for key in sorted(lookup, key=len, reverse=True):
        compact = key.replace("_", "")
        if len(compact) < 6 or key in _BOTANICAL_BLEND_GENERIC_KEYS:
            continue
        pattern = re.compile(
            r"(?<![a-z0-9])" + re.escape(key.replace("_", " ")) + r"(?![a-z0-9])"
        )
        patterns.append((key, pattern, lookup[key]))
    return tuple(patterns)


def _botanical_child_identity(name: Any) -> Optional[Dict[str, str]]:
    text = _norm(name)
    if not text:
        return None
    lookup = _botanical_identity_lookup()
    variants = {
        text,
        _slug(text),
        _norm(re.sub(r"\([^)]*\)", " ", text)),
        _slug(re.sub(r"\([^)]*\)", " ", text)),
    }
    stripped = _BOTANICAL_BLEND_NAME_STRIP_RE.sub(" ", text)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    variants.update({stripped, _slug(stripped)})
    for variant in variants:
        if variant in lookup:
            return lookup[variant]

    # Conservative phrase fallback for labels like "Milk thistle seed extract".
    # Require a non-generic key with enough characters so broad terms ("tea",
    # "root", "blend") cannot create botanical ownership by substring alone.
    for _, pattern, identity in _botanical_phrase_patterns():
        if pattern.search(text):
            return identity
    return None


@lru_cache(maxsize=1)
def _iqm_index() -> Dict[str, Dict[str, Any]]:
    try:
        raw = json.loads(_IQM_PATH.read_text())
    except Exception:  # pragma: no cover - missing data degrades to empty
        return {}
    return {str(key): value for key, value in raw.items() if isinstance(value, dict)}


def _form_quality_from_iqm(canonical_id: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve conservative form-quality fields for product evidence rows.

    Blend-anchor evidence is the compatibility bridge for current enriched
    blobs: dose can be known at a parent/blend level while no IQD scorable row
    exists. When the anchor canonical maps to IQM, carry label-supported form
    quality into the scoring row so Formulation does not see a false zero.
    Unmapped/generic blend headers return no credit.
    """
    entry = _iqm_index().get(_slug(canonical_id))
    forms = _safe_dict(entry.get("forms")) if entry else {}
    if not forms:
        return {}

    text = _norm(_row_text(context))
    candidates: List[tuple[int, int, float, str, Dict[str, Any]]] = []
    fallback: List[tuple[float, str, Dict[str, Any]]] = []
    for form_name, form in forms.items():
        if not isinstance(form, dict):
            continue
        bio = _as_float(form.get("bio_score"), None)
        score = _as_float(form.get("score"), bio)
        quality = bio if bio is not None else score
        if quality is None:
            continue
        fallback.append((float(quality), str(form_name), form))
        aliases = [form_name] + [
            str(alias)
            for alias in _safe_list(form.get("aliases") or form.get("form_aliases"))
            if alias
        ]
        for alias in aliases:
            alias_norm = _norm(alias)
            if alias_norm and alias_norm in text:
                specificity = 0 if "unspecified" in _norm(form_name) else 1
                candidates.append((specificity, len(alias_norm), float(quality), str(form_name), form))

    chosen_name = ""
    chosen: Dict[str, Any] = {}
    if candidates:
        _, _, _, chosen_name, chosen = sorted(candidates, key=lambda row: (row[0], row[1], row[2]), reverse=True)[0]
    elif len(fallback) == 1:
        _, chosen_name, chosen = fallback[0]
    elif fallback:
        _, chosen_name, chosen = sorted(fallback, key=lambda row: row[0])[0]
    if not chosen:
        return {}

    bio = _as_float(chosen.get("bio_score"), None)
    score = _as_float(chosen.get("score"), bio)
    out: Dict[str, Any] = {
        "matched_form": chosen_name,
        "generic_form_quality_credit": True,
    }
    if bio is not None:
        out["bio_score"] = bio
    if score is not None:
        out["score"] = score
    if "natural" in chosen:
        out["natural"] = bool(chosen.get("natural"))
    category = entry.get("category_enum") or entry.get("category")
    if category:
        out["category"] = category
    return out


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
    item = {
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
    for field in (
        "raw_taxonomy",
        "forms",
        "matched_form",
        "category",
        "dsld_category",
        "standardName",
        "standard_name",
        "raw_source_text",
    ):
        if field in row and row.get(field) not in (None, ""):
            item[field] = deepcopy(row.get(field))
    return item


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
    if _trustworthy_omega_parent_row(row, canonical):
        return True
    return not canonical and _is_omega_aggregate_row(row) and not _source_is_non_epa_dha_oil(row)


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
        str(row.get(key) or "")
        for key in ("name", "standardName", "standard_name", "canonical_id", "raw_source_text", "category")
    )
    return bool(_PROBIOTIC_IDENTITY_RE.search(text))


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


def _loose_identity_named_in_product_title(product: Dict[str, Any], row: Dict[str, Any]) -> bool:
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
    title_tokens |= {token[:-1] for token in title_tokens if token.endswith("s") and len(token) >= 5}
    identity_tokens: set[str] = set()
    for value in (
        row.get("name"),
        row.get("standardName"),
        row.get("standard_name"),
        row.get("raw_source_text"),
        row.get("canonical_id"),
    ):
        for token in re.split(r"[^a-z0-9]+", _norm(value).replace("_", " ")):
            if len(token) < 4:
                continue
            identity_tokens.add(token)
            if token.endswith("s") and len(token) >= 5:
                identity_tokens.add(token[:-1])
    return bool(title_tokens & identity_tokens)


def _title_embedded_single_active_mass(
    product: Dict[str, Any],
    row: Dict[str, Any],
    candidate_rows: List[Dict[str, Any]],
) -> tuple[Optional[float], Optional[str]]:
    """Conservative title-dose fallback for single-active labels.

    Some DSLD rows carry the dose only in the product name ("Tocotrienols
    50 mg") while the structured active row is 0/NP. This fallback is
    intentionally narrow so broad titles like "1300 mg Omega 3-6-9" do not
    assign a product-level mass to one child ingredient.
    """
    title = str(product.get("product_name") or product.get("fullName") or "")
    matches = list(_TITLE_MASS_RE.finditer(title))
    if len(matches) != 1:
        return None, None
    path = str(row.get("raw_source_path") or "")
    if not path:
        return None, None
    anchor_canonical, _ = _anchor_identity(row)
    if not anchor_canonical:
        return None, None
    if _positive_quantity(row) is not None:
        return None, None
    if not _loose_identity_named_in_product_title(product, row):
        return None, None

    unique_identity_paths = {
        str(candidate.get("raw_source_path") or f"_idx_{idx}")
        for idx, candidate in enumerate(candidate_rows)
        if isinstance(candidate, dict)
        and _anchor_identity(candidate)[0]
        and _norm(candidate.get("cleaner_row_role")) == "active_scorable"
        and candidate.get("score_eligible_by_cleaner") is True
    }
    if len(unique_identity_paths) != 1:
        return None, None

    match = matches[0]
    value = _as_float(match.group("value").replace(",", ""), None)
    if value is None or value <= 0:
        return None, None
    unit = match.group("unit")
    return value, unit


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


def _blend_total_amount_unit(blend: Dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    if blend.get("blend_total_mg") is not None:
        return _as_float(blend.get("blend_total_mg"), None), "mg"
    for key in ("total_weight", "amount", "quantity"):
        value = _as_float(blend.get(key), None)
        if value is not None and value > 0:
            return value, str(blend.get("unit") or blend.get("unit_normalized") or "mg")
    return None, None


def _blend_child_names(blend: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for child in _safe_list(blend.get("child_ingredients")):
        if isinstance(child, dict):
            name = child.get("name") or child.get("ingredient")
        else:
            name = child
        if name:
            names.append(str(name))
    evidence = _safe_dict(blend.get("evidence"))
    for key in ("ingredients_without_amounts", "children_without_amounts"):
        for child in _safe_list(evidence.get(key) or blend.get(key)):
            name = child.get("name") or child.get("ingredient") if isinstance(child, dict) else child
            if name:
                names.append(str(name))
    for key in ("ingredients_with_amounts", "children_with_amounts"):
        for child in _safe_list(evidence.get(key) or blend.get(key)):
            if not isinstance(child, dict):
                continue
            name = child.get("name") or child.get("ingredient")
            if name:
                names.append(str(name))
    out: List[str] = []
    seen = set()
    for name in names:
        key = _slug(name)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def _derive_top_level_botanical_blend_evidence(
    product: Dict[str, Any],
    blocked_paths: set[str],
) -> List[Dict[str, Any]]:
    """Compatibility bridge for enriched blobs that have blend detail but no
    IQD skipped parent/child rows.

    Emits a conservative product-level ``blend_anchor_mass`` only when the label
    discloses a blend total and a child name resolves to a therapeutic botanical.
    The total remains blend-level evidence; downstream botanical dose scores it
    as ``blend_total_only``, never as a verified per-ingredient clinical dose.
    """
    blends = _safe_list(product.get("proprietary_blends"))
    if not blends:
        blends = _safe_list(_safe_dict(product.get("proprietary_data")).get("blends"))
    evidence: List[Dict[str, Any]] = []
    for index, blend in enumerate(blends):
        if not isinstance(blend, dict):
            continue
        amount, unit = _blend_total_amount_unit(blend)
        if amount is None or amount <= 0 or not _unit_is_mass(unit):
            continue
        source_path = str(
            blend.get("source_path")
            or blend.get("source_field")
            or f"proprietary_blends[{index}]"
        )
        linked_paths = {
            source_path,
            *{str(path) for path in _safe_list(blend.get("source_fields")) if path},
        }
        if linked_paths & blocked_paths:
            continue
        botanical_child = None
        child_name = ""
        for name in _blend_child_names(blend):
            candidate = _botanical_child_identity(name)
            if candidate and has_therapeutic_reference(
                candidate["canonical_id"],
                candidate["name"],
            ):
                botanical_child = candidate
                child_name = name
                break
        if not botanical_child:
            continue
        row = {
            "name": child_name or botanical_child["name"],
            "canonical_id": botanical_child["canonical_id"],
            "canonical_source_db": "botanical_ingredients",
            "source_section": "proprietary_blends",
            "raw_source_path": source_path,
            "raw_source_text": child_name or botanical_child["name"],
            "raw_taxonomy": {
                "category": "botanical",
                "ingredientGroup": botanical_child["name"],
                "forms": [{"name": child_name or botanical_child["name"], "category": "botanical"}],
            },
            "forms": [{"name": child_name or botanical_child["name"], "category": "botanical"}],
        }
        item = _evidence_base(
            row=row,
            evidence_type="blend_anchor_mass",
            canonical_id=botanical_child["canonical_id"],
            clean_identity_id=botanical_child["canonical_id"],
            scoring_parent_id=botanical_child["canonical_id"],
            dose_value=amount,
            dose_unit=str(unit),
            evidence_scope="blend_level",
            confidence="low",
            reason="proprietary_blend_total_from_botanical_child",
            name=child_name or botanical_child["name"],
        )
        for path in sorted(linked_paths):
            if path and path not in item["linked_rows"]:
                item["linked_rows"].append(path)
        item["anchor_risk_class"] = "botanical_or_standardized"
        evidence.append(item)
    return evidence


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
    has_explicit_epa_dha_row = any(_trustworthy_epa_dha_row(row) for row in active_rows)

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
    for row in skipped_rows:
        path = str(row.get("raw_source_path") or "")
        if path and (path in scorable_paths or path in special_evidence_paths):
            continue
        canonical = _norm(row.get("canonical_id"))
        activity_value, activity_unit = _extract_enzyme_activity(row)
        if activity_value is None or not activity_unit:
            continue
        special_evidence_paths.add(path)
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
            reason="enzyme_activity_unit_from_skipped_label_notes",
            name=row.get("name") or "Enzyme activity",
            dose_class="enzyme_activity",
        ))

    for row in skipped_rows:
        path = str(row.get("raw_source_path") or "")
        if path and (path in scorable_paths or path in special_evidence_paths):
            continue
        title_dose_value, title_dose_unit = _title_embedded_single_active_mass(
            product,
            row,
            candidate_rows,
        )
        if title_dose_value is None or not title_dose_unit:
            continue
        anchor_canonical, anchor_name = _anchor_identity(row)
        if not anchor_canonical:
            continue
        special_evidence_paths.add(path)
        evidence.append(_evidence_base(
            row=row,
            evidence_type="blend_anchor_mass",
            canonical_id=anchor_canonical,
            clean_identity_id=_norm(row.get("canonical_id")) or anchor_canonical,
            scoring_parent_id=anchor_canonical,
            dose_value=title_dose_value,
            dose_unit=str(title_dose_unit),
            evidence_scope="row_level",
            confidence="low",
            reason="single_active_title_embedded_mass",
            name=anchor_name or row.get("name") or "Title embedded dose",
        ))

    for parent in skipped_rows:
        parent_path = str(parent.get("raw_source_path") or "")
        if not parent_path or parent_path in scorable_paths or parent_path in special_evidence_paths:
            continue
        item = _derive_blend_header_anchor_from_nested_child(product, parent, candidate_rows)
        if item:
            special_evidence_paths.add(parent_path)
            evidence.append(item)

    for item in _derive_top_level_botanical_blend_evidence(
        product,
        scorable_paths | special_evidence_paths,
    ):
        path = str(item.get("raw_source_path") or "")
        if path:
            special_evidence_paths.add(path)
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
        native_evidence_rows = _safe_list(evidence.get("items") or evidence.get("evidence"))
        if not native_evidence_rows and evidence:
            native_evidence_rows = [evidence]
    else:
        native_evidence_rows = _safe_list(evidence)
    native_evidence_rows = [deepcopy(item) for item in native_evidence_rows if isinstance(item, dict)]
    derived_evidence_rows = derive_product_scoring_evidence(product)

    def evidence_key(item: Dict[str, Any]) -> tuple[Any, ...]:
        return (
            item.get("evidence_type"),
            item.get("canonical_id") or item.get("evidence_canonical_id"),
            item.get("raw_source_path"),
            item.get("dose_value"),
            item.get("dose_unit"),
        )

    derived_by_key = {evidence_key(item): item for item in derived_evidence_rows}
    context_fields = (
        "raw_taxonomy",
        "forms",
        "matched_form",
        "category",
        "dsld_category",
        "standardName",
        "standard_name",
        "raw_source_text",
        "anchor_risk_class",
    )
    for item in native_evidence_rows:
        derived_item = derived_by_key.get(evidence_key(item))
        if not derived_item:
            continue
        for field in context_fields:
            if item.get(field) in (None, "") and derived_item.get(field) not in (None, ""):
                item[field] = deepcopy(derived_item.get(field))

    evidence_rows = native_evidence_rows + derived_evidence_rows

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
        if evidence_type == "blend_anchor_mass" and not row.get("bio_score"):
            quality = _form_quality_from_iqm(row.get("canonical_id"), row)
            if quality:
                row.update(quality)
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

    # Strict mode trusts the stamped identity disposition over a possibly-stale
    # scoreable_identity flag: a conflict/missing-display row that still claims
    # scoreable_identity=True is a violated upstream invariant and must not be
    # scored. Old batches (no disposition) stay tolerated; non-strict callers
    # keep the legacy scoreable_identity-only behavior.
    if strict:
        disposition = row.get("identity_disposition")
        if disposition is not None:
            if disposition not in IDENTITY_DISPOSITIONS:
                reason = f"invalid_identity_disposition:{disposition}"
                findings.append(reason)
                return False, _reject(row, reason), findings
            if not is_identity_scoreable(disposition):
                reason = f"identity_disposition_not_scoreable:{disposition}"
                findings.append(reason)
                return False, _reject(row, reason), findings

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
        # Design contract: an unresolved identity (conflict / missing display)
        # cannot be recovered into scoring — it must not drive scoring, evidence,
        # interactions, or routing. The strict _evaluate_row guard is the
        # backstop; skipping recovery here keeps a doomed row from ever claiming
        # scoreable_identity. Rows with no stamped disposition stay recoverable.
        disposition = row.get("identity_disposition")
        if disposition is not None and not is_identity_scoreable(disposition):
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
_CLASSIFICATION_ANIMAL_SOURCE_RE = re.compile(
    r"\b("
    r"animal|bovine|porcine|beef|chicken|fish|marine|gelatin|cartilage|"
    r"kidney(?!\s+bean)|liver|heart|thymus|pancreas|pituitary|adrenal|spleen|"
    r"organ|gland|glandular"
    r")\b",
    re.IGNORECASE,
)
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
    **{canonical: "sports_active" for canonical in _CREATINE_CANONICALS},
    "beta-alanine": "sports_active",
    "beta_alanine": "sports_active",
    "l_citrulline": "sports_active",
    "hmb": "sports_active",
    "collagen": "collagen",
    "collagen_peptides": "collagen",
    "hydrolyzed_collagen": "collagen",
    "undenatured_type_ii_collagen": "collagen",
    "digestive_enzymes": "enzyme",
    "glucosamine": "generic_active",
    "nattokinase": "enzyme",
}
_CLASSIFICATION_ISOLATED_BOTANICAL_MARKERS = {
    "activated_charcoal",
    "caffeine",
    "ceramides",
    "d_limonene",
    "lycopene",
    "lutein",
    "policosanol",
    "raspberry_ketones",
    "resveratrol",
    "sulforaphane",
    "theobromine",
    "zeaxanthin",
}
_CLASSIFICATION_ISOLATED_BOTANICAL_TEXT_RE = re.compile(
    r"\b(yohimbine|quercetin|nattokinase)\b",
    re.IGNORECASE,
)
_CLASSIFICATION_NON_BOTANICAL_GENERIC_CANONICALS = {
    "glucosamine",
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
_ROUTE_PROBIOTIC_NAME_RE = re.compile(
    r"\b(probiotic|probiotics|synbiotic|synbiotics|acidophilus|lactobacillus|"
    r"bifidobacterium|saccharomyces|bacillus)\b",
    re.IGNORECASE,
)
_ROUTE_PROBIOTIC_ADJUNCT_PANEL_MAX = 2
_ROUTE_PROBIOTIC_HIGH_CFU_BILLIONS = 1.0
_ROUTE_PROBIOTIC_PURE_STRAIN_MIN = 2
_ROUTE_PROBIOTIC_VAGUE_TAXONOMY = frozenset({"", "general_supplement", "probiotic"})
_ROUTE_NON_PROBIOTIC_HERO_TITLE_RE = re.compile(
    r"\b(zinc|magnesium|calcium|iron|potassium|selenium|copper|chromium|iodine|"
    r"vitamin|biotin|folate|folic|niacin|thiamine|riboflavin|"
    r"d2|d3|k2|b12|"
    r"protein|whey|casein|collagen|gelatin|"
    r"enzyme|enzymes|"
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
_ROUTE_TRUE_PROTEIN_NAME_RE = re.compile(
    r"\b(whey|casein|pea\s+protein|rice\s+protein|soy\s+protein|plant(?:-based)?\s+protein|"
    r"protein\s+(?:powder|isolate|concentrate|hydrolysate|hydrolyzed|blend|matrix)|"
    r"mass\s+gainer|gainer)\b",
    re.IGNORECASE,
)
_ROUTE_COLLAGEN_TITLE_RE = re.compile(r"\b(collagen|gelatin|hyaluronic)\b", re.IGNORECASE)
_ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE = re.compile(
    r"\b(creatine|beta[\s-]?alanine|citrulline|hmb|bcaa|eaa|essential amino|branched chain)\b",
    re.IGNORECASE,
)
_ROUTE_SPORTS_NAME_EXCLUSION_RE = re.compile(
    r"\b(nac|n-acetyl|theanine|tryptophan|5-htp|sam-e|sleep|calm|mood|stress|"
    r"digestive|enzyme|enzymes|keratin|lactoferrin|collagen)\b",
    re.IGNORECASE,
)
_ROUTE_FIBER_DIGESTIVE_NAME_RE = re.compile(
    r"\b(fiber|fibre|psyllium|inulin|prebiotic|digestive\s+enzymes?|digestive\s+fiber)\b",
    re.IGNORECASE,
)
_ROUTE_B_COMPLEX_EXCLUSION_RE = re.compile(
    r"\b(pre[\s-]?workout|fat\s*burn|thermogenic|weight\s*loss|liver|stress|mood)\b",
    re.IGNORECASE,
)
_ROUTE_B_COMPLEX_DISQUALIFY_CANONICALS = {
    "caffeine",
    "green_tea_extract",
    "green_coffee_bean",
    "garcinia_cambogia",
    "yohimbe",
    "yohimbine",
    "synephrine",
}
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
    "vitamin_b5_pantothenic",
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
_ROUTE_NON_B_VITAMIN_CANONICALS = {
    "vitamin_a",
    "vitamin_c",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "vitamin_k1",
    "vitamin_k2",
}
_ROUTE_MINERAL_CANONICALS = {
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
}
_ROUTE_MULTI_SUPPORT_CANONICALS = {"choline", "folate"}
_ROUTE_LEGACY_MULTIVITAMIN_MIN_MULTI_NUTRIENTS = 5
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
    "docosapentaenoic_acid_dpa",
    "dpa",
    "omega_6_fatty_acids",
    "omega_9_fatty_acids",
    "borage_seed_oil",
    "evening_primrose_oil",
}
_ROUTE_OMEGA_SOFT_ADJUNCT_CANONICALS = {
    "vitamin_d",
    "vitamin_d3",
    "cholecalciferol",
    "vitamin_e",
    "mixed_tocopherols",
    "d_alpha_tocopherol",
    # Astaxanthin is a trace carotenoid antioxidant naturally present in krill oil
    # and routinely added to algal/fish oil to protect EPA/DHA from oxidation; it
    # is an adjunct, not a competing identity (e.g. Minami VeganDHA: DHA 400 +
    # DPA 140 + astaxanthin 1.5 mg).
    "astaxanthin",
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
    *_CREATINE_CANONICALS,
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
    "b_complex": "b_complex",
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
    "fiber_digestive": "fiber_digestive",
    "sleep_support": "generic",
    "immune_support": "generic",
    "joint_support": "generic",
    "beauty_hair_skin_nails": "generic",
    "general_supplement": "generic",
}
_ROUTE_LEGACY_MULTI_FALLBACK_EXCLUDED_PRIMARY_TYPES = {
    "amino_acid",
    "collagen",
    "fiber_digestive",
    "greens_powder",
    "omega_3",
    "pre_workout",
    "probiotic",
    "protein_powder",
}
_ROUTE_EXPLICIT_MULTIVITAMIN_NAME_RE = re.compile(
    r"\b(multivitamin|multi-vitamin|multi vitamin|multimineral)\b",
    re.IGNORECASE,
)


def _valid_classification_origin(origin: Any) -> str:
    origin_norm = _norm(origin) or "compatibility_derived"
    return origin_norm if origin_norm in SCORING_CLASSIFICATION_ORIGINS else "compatibility_derived"


def _embedded_native_scoring_classification(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a valid persisted native classification contract, if present."""
    embedded = product.get("product_scoring_classification") if isinstance(product, dict) else None
    if not isinstance(embedded, dict):
        return None
    if embedded.get("classification_schema_version") != SCORING_CLASSIFICATION_SCHEMA_VERSION:
        return None
    if _norm(embedded.get("classification_origin")) != "native_enrichment":
        return None
    if any(field not in embedded for field in SCORING_CLASSIFICATION_REQUIRED_FIELDS):
        return None

    route = _norm(embedded.get("route_module"))
    confidence = _norm(embedded.get("route_confidence"))
    if route not in SCORING_ROUTE_MODULES:
        return None
    if confidence not in SCORING_ROUTE_CONFIDENCE:
        return None
    if embedded.get("classification_failed") is True and route != "generic":
        return None
    if not isinstance(embedded.get("route_evidence"), list):
        return None
    if not isinstance(embedded.get("ingredients"), list):
        return None
    if not isinstance(embedded.get("profile_eligibility"), dict):
        return None
    try:
        derived_route, _, _ = _classify_route_module(product)
    except Exception:
        derived_route = None
    if derived_route in SCORING_ROUTE_MODULES and route != derived_route:
        return None

    return deepcopy(embedded)


def _route_scoring_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    cached_rows = _safe_list(_safe_dict(product or {}).get(_ROUTE_SCORING_ROWS_CACHE_KEY))
    if cached_rows:
        return [row for row in cached_rows if isinstance(row, dict)]
    try:
        return [
            row for row in get_scoring_ingredients(product or {}, strict=True).rows
            if isinstance(row, dict)
        ]
    except Exception:
        return []


def _route_raw_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    ingredient_quality_data = (product or {}).get("ingredient_quality_data")
    if isinstance(ingredient_quality_data, dict):
        for key in ("ingredients_scorable", "ingredients"):
            value = ingredient_quality_data.get(key)
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
    elif isinstance(ingredient_quality_data, list):
        rows.extend(row for row in ingredient_quality_data if isinstance(row, dict))

    active_ingredients = (product or {}).get("active_ingredients")
    if isinstance(active_ingredients, list):
        rows.extend(row for row in active_ingredients if isinstance(row, dict))
    return rows


def _route_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = _route_scoring_rows(product)
    seen = {id(row) for row in rows}
    for row in _route_raw_rows(product):
        if id(row) not in seen:
            rows.append(row)
            seen.add(id(row))
    return rows


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
    for row in _route_rows(product):
        if row.get("scoring_input_kind") == "product_level_evidence":
            continue
        canonical = _norm(row.get("canonical_id"))
        if canonical and _route_has_positive_quantity(row):
            canonicals.add(canonical)
    return canonicals


def _route_omega_panel_counts(product: Dict[str, Any]) -> tuple[int, int]:
    omega_rows = 0
    total_rows = 0
    for row in _route_rows(product):
        if (
            row.get("scoring_input_kind") == "product_level_evidence"
            and _norm(row.get("evidence_type")) != "omega_epa_dha_aggregate"
        ):
            continue
        canonical = _norm(row.get("canonical_id"))
        if not canonical or not _route_has_positive_quantity(row):
            continue
        total_rows += 1
        if canonical in _ROUTE_OMEGA_INGREDIENT_CANONICALS and _trustworthy_epa_dha_row(row):
            omega_rows += 1
    return omega_rows, total_rows


def _route_has_primary_omega_panel(product: Dict[str, Any]) -> bool:
    omega_rows, total_rows = _route_omega_panel_counts(product)
    if omega_rows <= 0 or total_rows <= 0:
        return False
    return omega_rows == total_rows or (omega_rows / total_rows) >= 0.5


def _route_has_any_epa_dha_row(product: Dict[str, Any]) -> bool:
    for row in _route_rows(product):
        if _trustworthy_epa_dha_row(row):
            return True
    return False


def _route_has_omega_scoring_evidence(product: Dict[str, Any]) -> bool:
    for row in _route_rows(product):
        if _norm(row.get("evidence_type")) == "omega_epa_dha_aggregate":
            return True
    return False


def _route_has_non_omega_product_level_evidence(
    product: Dict[str, Any],
    *,
    allow_omega_companions: bool = False,
) -> bool:
    for row in _route_rows(product):
        if row.get("scoring_input_kind") != "product_level_evidence":
            continue
        evidence_type = _norm(row.get("evidence_type"))
        canonical = _norm(row.get("canonical_id"))
        if evidence_type == "omega_epa_dha_aggregate":
            continue
        if canonical in _ROUTE_OMEGA_INGREDIENT_CANONICALS or canonical in _ROUTE_OMEGA_PARENT_CANONICALS:
            continue
        # A marine fish oil's own companion fatty acids (oleic/omega-9, GLA, etc.)
        # and oxidation-protector adjuncts (vitamin D/E) often surface as blend-
        # anchor product evidence; they must not count as disqualifying non-omega
        # evidence when the taxonomy already says omega_3 with a real EPA/DHA row.
        if allow_omega_companions and (
            canonical in _ROUTE_NON_EPA_DHA_FATTY_ACID_CANONICALS
            or canonical in _ROUTE_OMEGA_SOFT_ADJUNCT_CANONICALS
        ):
            continue
        return True
    return False


def _route_has_non_epa_dha_fatty_acid_panel(product: Dict[str, Any]) -> bool:
    if _route_has_any_epa_dha_row(product):
        return False
    for row in _route_rows(product):
        canonical = _norm(row.get("canonical_id"))
        if canonical in _ROUTE_NON_EPA_DHA_FATTY_ACID_CANONICALS:
            return True
        if (
            canonical in _ROUTE_OMEGA_PARENT_CANONICALS | _ROUTE_OMEGA_INGREDIENT_CANONICALS
            and _source_is_non_epa_dha_oil(row)
            and not _source_has_epa_dha_identity(row)
        ):
            return True
    return False


def _route_has_non_omega_positive_scorable_panel(
    product: Dict[str, Any],
    *,
    allow_soft_omega_adjuvants: bool = False,
) -> bool:
    for row in _route_rows(product):
        if row.get("scoring_input_kind") == "product_level_evidence":
            continue
        canonical = _norm(row.get("canonical_id"))
        if not canonical or not _route_has_positive_quantity(row):
            continue
        if canonical in _ROUTE_OMEGA_INGREDIENT_CANONICALS or canonical in _ROUTE_OMEGA_PARENT_CANONICALS:
            continue
        if canonical in _ROUTE_NON_EPA_DHA_FATTY_ACID_CANONICALS:
            continue
        if allow_soft_omega_adjuvants and canonical in _ROUTE_OMEGA_SOFT_ADJUNCT_CANONICALS:
            continue
        return True
    return False


def _route_has_omega_taxonomy_with_trustworthy_epa_dha_panel(product: Dict[str, Any]) -> bool:
    if _primary_type(product) != "omega_3":
        return False
    if not _route_has_any_epa_dha_row(product):
        return False
    if _route_has_non_omega_product_level_evidence(product, allow_omega_companions=True):
        return False
    return not _route_has_non_omega_positive_scorable_panel(
        product,
        allow_soft_omega_adjuvants=True,
    )


def _route_probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    payload = (product or {}).get("probiotic_data") or (product or {}).get("probiotic_detail") or {}
    return payload if isinstance(payload, dict) else {}


def _route_non_probiotic_scorable_count(
    product: Dict[str, Any], *, require_disclosed: bool = False
) -> int:
    """Count scorable active rows that are NOT probiotic strains.

    When ``require_disclosed`` is True, rows without a positive disclosed amount
    (quantity == 0 / undisclosed) are excluded. Undisclosed blend children
    otherwise inflate the panel and demote a genuine probiotic, so the disclosed
    count gates the pure-strain promotion paths while the full count still
    governs strain-vs-panel dominance.
    """
    count = 0
    for row in _route_scoring_rows(product):
        if not isinstance(row, dict):
            continue
        taxonomy = _safe_dict(row.get("raw_taxonomy"))
        category = _norm(taxonomy.get("category") or row.get("category"))
        if category in {"probiotic", "probiotics", "bacteria"}:
            continue
        if _norm(row.get("dose_class")) == "probiotic_cfu":
            continue
        if _norm(row.get("evidence_type")) == "probiotic_cfu":
            continue
        if _has_probiotic_identity_text(row):
            continue
        if _is_probiotic_support_row(row):
            continue
        if require_disclosed and not _route_has_positive_quantity(row):
            continue
        count += 1
    return count


def _route_title_has_non_probiotic_hero(name_text: str) -> bool:
    return bool(_ROUTE_NON_PROBIOTIC_HERO_TITLE_RE.search(name_text or ""))


def _route_title_hero_precedes_probiotic_signal(name_text: str) -> bool:
    hero = _ROUTE_NON_PROBIOTIC_HERO_TITLE_RE.search(name_text or "")
    probiotic = _ROUTE_PROBIOTIC_NAME_RE.search(name_text or "")
    return bool(hero and probiotic and hero.start() < probiotic.start())


def _route_has_non_probiotic_hero(product: Dict[str, Any], name_text: str) -> bool:
    primary_type = _primary_type(product)
    if primary_type and primary_type not in _ROUTE_PROBIOTIC_VAGUE_TAXONOMY:
        return True
    return _route_title_has_non_probiotic_hero(name_text)


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
    primary_type = _primary_type(product)

    if not is_product or strain_count <= 0:
        return False

    non_probiotic_panel = _route_non_probiotic_scorable_count(product)
    # Disclosed (positive-quantity) panel for the pure-strain promotion paths and
    # the small-adjunct-with-name gate. Undisclosed (quantity == 0) blend rows
    # must not demote a genuine probiotic (Kids 5 Billion CFU: 5 strains buried
    # under ~23 zero-qty superfood rows; Probiotic GX: 1 strain + a disclosed
    # enzyme-blend header whose enzyme children are zero-qty). The FULL count
    # still governs strain-vs-panel dominance below, so a real multivitamin with
    # a few undisclosed rows is not promoted by its strains.
    disclosed_non_probiotic_panel = _route_non_probiotic_scorable_count(
        product, require_disclosed=True
    )
    if (
        disclosed_non_probiotic_panel == 0
        and strain_count >= _ROUTE_PROBIOTIC_PURE_STRAIN_MIN
        and not _route_has_non_probiotic_hero(product, name_text)
    ):
        return True

    if (
        primary_type == "probiotic"
        and disclosed_non_probiotic_panel == 0
        and strain_count >= 1
        and not _route_has_non_probiotic_hero(product, name_text)
    ):
        return True

    if not (has_cfu or name_signal):
        return False

    if primary_type and primary_type not in _ROUTE_PROBIOTIC_VAGUE_TAXONOMY and not name_signal:
        if not (high_cfu and non_probiotic_panel <= _ROUTE_PROBIOTIC_ADJUNCT_PANEL_MAX):
            return False

    if name_signal and non_probiotic_panel > 0 and _route_title_hero_precedes_probiotic_signal(name_text):
        return False

    if non_probiotic_panel > 0 and not name_signal:
        if _route_title_has_non_probiotic_hero(name_text):
            return False
        if not high_cfu:
            return False

    if strain_count >= non_probiotic_panel:
        return True
    if disclosed_non_probiotic_panel <= _ROUTE_PROBIOTIC_ADJUNCT_PANEL_MAX and name_signal:
        return True
    return False


def _route_product_lacks_epa_dha_identity(product: Dict[str, Any]) -> bool:
    """True when the product source is an explicit non-EPA/DHA plant/seed/MCT oil
    (flax/ALA/chia/hemp/fiber/seed/MCT/coconut) with NO marine source and NO
    explicit EPA/DHA token — plant 'omega-3' (ALA), which must route generic even
    if a panel row was mis-canonicalized to epa/dha/fish_oil upstream."""
    parts = [_route_product_label_text(product)]
    for row in _route_rows(product):
        if isinstance(row, dict):
            parts.append(_row_source_text(row))
    probe = {"name": " ".join(p for p in parts if p)}
    return bool(
        _NON_EPA_DHA_SOURCE_RE.search(_row_source_text(probe))
        and not _source_has_epa_dha_identity(probe)
        and not _source_is_marine_omega_parent(probe)
    )


def _route_is_omega_class(product: Dict[str, Any], name_text: str) -> bool:
    # Hard guard: plant 'omega-3' (ALA: flax/chia/hemp/fiber/seed/MCT/coconut) with
    # no marine source and no explicit EPA/DHA token must route generic, never the
    # EPA/DHA omega module — even when primary_type=='omega_3' or a row was
    # mis-canonicalized upstream (the row-level checks below run too late because
    # _route_has_primary_omega_panel short-circuits on the polluted canonical).
    if _route_product_lacks_epa_dha_identity(product):
        return False
    if _route_has_primary_omega_panel(product):
        return True
    # A confident omega_3 taxonomy with a trustworthy EPA/DHA row can still be
    # omega when companion fatty acids (omega-6/9, GLA, DPA) dilute EPA/DHA below
    # the primary-panel count gate. Broad non-omega stacks with incidental DHA
    # stay generic via the non-omega-panel check inside this predicate.
    if _route_has_omega_taxonomy_with_trustworthy_epa_dha_panel(product):
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
    if _ROUTE_B_COMPLEX_EXCLUSION_RE.search(name_text or ""):
        return False

    b_vitamins: set[str] = set()
    non_b_scorable = 0
    disqualifying_actives: set[str] = set()
    for row in _route_scoring_rows(product):
        canonical = _norm(row.get("canonical_id"))
        if not canonical:
            continue
        if canonical in _ROUTE_B_VITAMIN_CANONICALS:
            b_vitamins.add(canonical)
        else:
            non_b_scorable += 1
            if canonical in _ROUTE_B_COMPLEX_DISQUALIFY_CANONICALS:
                disqualifying_actives.add(canonical)
    if disqualifying_actives:
        return False
    if "b-complex" in lowered or "b complex" in lowered:
        return len(b_vitamins) >= 3 and non_b_scorable <= 2
    return len(b_vitamins) >= 4 and non_b_scorable <= 1


def _route_is_multivitamin_eligible(product: Dict[str, Any], name_text: str) -> bool:
    """Guard the `multivitamin` taxonomy route the same way omega/sports/b_complex
    are guarded — by content, not the native primary_type alone. A real multivitamin
    has a broad multi-nutrient panel; a thin product mis-tagged `multivitamin` by
    taxonomy drift must not be crushed by the prenatal/multi panel-coverage floors.
    Explicit multi* naming is taken at its word (mirrors the b_complex name override)."""
    lowered = (name_text or "").lower()
    if (
        "multivitamin" in lowered
        or "multi-vitamin" in lowered
        or "multi vitamin" in lowered
        or "multimineral" in lowered
    ):
        return True
    canonicals = _route_positive_canonicals(product)
    if (
        len(canonicals & _ROUTE_MULTI_PANEL_CANONICALS)
        >= _ROUTE_LEGACY_MULTIVITAMIN_MIN_MULTI_NUTRIENTS
    ):
        return True
    if _primary_type(product) == "multivitamin":
        return (
            _route_positive_scorable_row_count(product)
            >= _ROUTE_MULTIVITAMIN_BROAD_PANEL_MIN
        )
    return False


def _route_read_legacy_multivitamin_type(product: Dict[str, Any]) -> str:
    payload = _safe_dict((product or {}).get("supplement_type"))
    return _norm(payload.get("type"))


def _route_multi_panel_group_count(canonicals: set[str]) -> int:
    groups = set()
    if canonicals & _ROUTE_B_VITAMIN_CANONICALS:
        groups.add("b_vitamins")
    if canonicals & _ROUTE_NON_B_VITAMIN_CANONICALS:
        groups.add("vitamins")
    if canonicals & _ROUTE_MINERAL_CANONICALS:
        groups.add("minerals")
    if canonicals & _ROUTE_MULTI_SUPPORT_CANONICALS:
        groups.add("support_nutrients")
    return len(groups)


def _route_has_broad_legacy_multivitamin_panel(product: Dict[str, Any]) -> bool:
    """Compatibility fallback for themed multi-packs.

    Some enriched products correctly retain legacy type=multivitamin while the
    normalized taxonomy uses the product theme (immune_support, sleep_support,
    herbal_botanical). Trust that legacy signal only when the physical panel is
    broad enough to be a real multivitamin, so old false positives stay generic.
    """
    if _route_read_legacy_multivitamin_type(product) != "multivitamin":
        return False
    if _primary_type(product) in _ROUTE_LEGACY_MULTI_FALLBACK_EXCLUDED_PRIMARY_TYPES:
        return False
    canonicals = _route_positive_canonicals(product)
    multi_nutrients = canonicals & _ROUTE_MULTI_PANEL_CANONICALS
    return (
        len(multi_nutrients) >= _ROUTE_LEGACY_MULTIVITAMIN_MIN_MULTI_NUTRIENTS
        and _route_positive_scorable_row_count(product) >= _ROUTE_MULTIVITAMIN_BROAD_PANEL_MIN
        and _route_multi_panel_group_count(multi_nutrients) >= 3
    )


def _route_positive_scorable_row_count(product: Dict[str, Any]) -> int:
    count = 0
    for row in _route_scoring_rows(product):
        if row.get("scoring_input_kind") == "product_level_evidence":
            continue
        if _route_has_positive_quantity(row):
            count += 1
    return count


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


def _route_has_product_level_protein_mass(product: Dict[str, Any]) -> bool:
    protein_ids = {"protein"} | _ROUTE_SPORTS_PROTEIN_CANONICALS
    for row in _route_scoring_rows(product):
        if row.get("scoring_input_kind") != "product_level_evidence":
            continue
        if _norm(row.get("evidence_type")) not in {"sports_primary_dose", "blend_anchor_mass"}:
            continue
        identities = {
            _norm(row.get("canonical_id")),
            _norm(row.get("evidence_canonical_id")),
            _norm(row.get("scoring_parent_id")),
            _norm(row.get("clean_identity_id")),
        }
        if identities & protein_ids and _route_has_positive_quantity(row):
            return True
    return False


def _route_has_product_level_single_sports_mass(product: Dict[str, Any]) -> bool:
    for row in _route_scoring_rows(product):
        if row.get("scoring_input_kind") != "product_level_evidence":
            continue
        if _norm(row.get("evidence_type")) not in {"sports_primary_dose", "blend_anchor_mass"}:
            continue
        identities = {
            _norm(row.get("canonical_id")),
            _norm(row.get("evidence_canonical_id")),
            _norm(row.get("scoring_parent_id")),
            _norm(row.get("clean_identity_id")),
        }
        if identities & _ROUTE_SPORTS_SINGLE_CANONICALS and _route_has_positive_quantity(row):
            return True
    return False


def _route_has_collagen_primary_identity(product: Dict[str, Any], name_text: str) -> bool:
    canonicals = _route_positive_canonicals(product)
    has_collagen_row = bool(canonicals & {"collagen", "collagen_peptides", "hydrolyzed_collagen"})
    has_collagen_title = bool(_ROUTE_COLLAGEN_TITLE_RE.search(name_text or ""))
    if not (has_collagen_row or has_collagen_title):
        return False
    if canonicals & _ROUTE_SPORTS_PROTEIN_CANONICALS:
        return False
    if _ROUTE_TRUE_PROTEIN_NAME_RE.search(name_text or "") and not has_collagen_title:
        return False
    return True


def _route_is_sports_class(product: Dict[str, Any], name_text: str) -> bool:
    primary_type = _primary_type(product)
    sports_intent = primary_type == "pre_workout" or bool(_ROUTE_SPORTS_PREWORKOUT_RE.search(name_text or ""))
    if _route_has_collagen_primary_identity(product, name_text):
        return False
    if _route_has_sports_primary_dose_evidence(product):
        return True

    # Route by sports IDENTITY, like omega: a confident pre_workout taxonomy, or an
    # unambiguous sports-hero name (creatine / beta-alanine / citrulline / HMB / BCAA /
    # EAA / pre-workout), is a sports product even when the ergogenic actives are
    # undisclosed in a proprietary blend or listed only as an aggregate. The existing
    # NAC/theanine/sleep/collagen exclusion still applies, and the name-only path must
    # not hijack a genuine multivitamin. Parts 2-3 (gate fail-open + dose credit for
    # disclosed non-classic actives) make this net-positive, which is why the earlier
    # routing-only version was reverted.
    if not _ROUTE_SPORTS_NAME_EXCLUSION_RE.search(name_text or ""):
        if primary_type == "pre_workout":
            return True
        if (
            _ROUTE_SPORTS_PREWORKOUT_RE.search(name_text or "")
            or _ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE.search(name_text or "")
        ) and not _route_is_multivitamin_eligible(product, name_text):
            return True

    canonicals = _route_positive_canonicals(product)
    if canonicals & _ROUTE_SPORTS_PROTEIN_CANONICALS:
        return primary_type == "protein_powder" or bool(_ROUTE_SPORTS_PROTEIN_NAME_RE.search(name_text or ""))
    if _route_has_product_level_protein_mass(product) and _ROUTE_SPORTS_PROTEIN_NAME_RE.search(name_text or ""):
        return True
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
        return sports_intent or bool(_ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE.search(name_text or ""))
    if _route_has_product_level_single_sports_mass(product):
        if _ROUTE_SPORTS_NAME_EXCLUSION_RE.search(name_text or ""):
            return False
        return sports_intent or bool(_ROUTE_SPORTS_SINGLE_ACTIVE_NAME_RE.search(name_text or ""))
    return False


def _classify_route_module(product: Dict[str, Any]) -> tuple[str, str, List[str]]:
    """Independent ScoringClassification v1 route decision.

    This mirrors the current v4 route semantics so migration can prove parity,
    but lives in the classification contract. The legacy router remains only as
    an audit comparison target.
    """
    primary_type = _primary_type(product)
    name_text = _route_name_text(product)

    if primary_type != "greens_powder" and _route_is_probiotic_class(product, name_text):
        return "probiotic", "profile_content:probiotic", ["probiotic_identity_or_cfu"]

    if _ROUTE_PRENATAL_KEYWORDS.search(_route_product_label_text(product)):
        if _route_has_primary_omega_panel(product):
            return "omega", "prenatal_title_with_primary_omega_panel", ["prenatal_title", "primary_omega_panel"]
        if _route_is_prenatal_multi_intent(product, name_text):
            return "multi_or_prenatal", "prenatal_multi_intent", ["prenatal_title", "multi_panel_or_taxonomy"]

    if _route_is_sports_class(product, name_text):
        return "sports", "profile_content:sports", ["sports_identity_or_dose"]

    if (
        _ROUTE_EXPLICIT_MULTIVITAMIN_NAME_RE.search(_route_product_label_text(product))
        and _route_is_multivitamin_eligible(product, name_text)
    ):
        return "multi_or_prenatal", "profile_content:explicit_multivitamin", ["explicit_multivitamin_name"]

    if (
        primary_type == "multivitamin"
        and _route_is_multivitamin_eligible(product, name_text)
    ):
        return "multi_or_prenatal", "taxonomy:multivitamin", ["taxonomy:multivitamin"]

    if _route_has_broad_legacy_multivitamin_panel(product):
        return (
            "multi_or_prenatal",
            "legacy_multivitamin_broad_panel",
            ["legacy_supplement_type:multivitamin", "broad_multi_panel"],
        )

    if _route_is_fiber_digestive_class(product, name_text):
        return "fiber_digestive", "profile_content:fiber_digestive", ["fiber_digestive_identity"]

    if primary_type:
        module = _ROUTE_TAXONOMY_TO_MODULE.get(primary_type)
        if module == "b_complex":
            if _route_is_b_complex_eligible(product, name_text):
                return "b_complex", f"taxonomy:{primary_type}:b_complex_validated", [f"taxonomy:{primary_type}", "b_complex_panel"]
            return "generic", "b_complex_taxonomy_without_route_eligible_panel", ["taxonomy:b_complex"]
        if module == "multi_or_prenatal":
            if primary_type == "multivitamin" and not _route_is_multivitamin_eligible(product, name_text):
                return "generic", "multivitamin_taxonomy_without_route_eligible_panel", ["taxonomy:multivitamin"]
            return "multi_or_prenatal", f"taxonomy:{primary_type}", [f"taxonomy:{primary_type}"]
        if module == "omega":
            if _route_is_omega_class(product, name_text):
                return "omega", f"taxonomy:{primary_type}:omega_validated", [f"taxonomy:{primary_type}", "omega_evidence"]
            return "generic", f"taxonomy:{primary_type}:omega_evidence_missing", [f"taxonomy:{primary_type}"]
        if module == "sports":
            if _route_is_sports_class(product, name_text):
                return "sports", f"taxonomy:{primary_type}:sports_validated", [f"taxonomy:{primary_type}", "sports_evidence"]
            return "generic", f"taxonomy:{primary_type}:sports_evidence_missing", [f"taxonomy:{primary_type}"]
        if module == "fiber_digestive":
            if _route_is_fiber_digestive_class(product, name_text):
                return "fiber_digestive", f"taxonomy:{primary_type}:fiber_digestive_validated", [f"taxonomy:{primary_type}", "fiber_digestive_identity"]
            return "generic", f"taxonomy:{primary_type}:fiber_digestive_evidence_missing", [f"taxonomy:{primary_type}"]
        if module == "generic":
            if _route_is_omega_class(product, name_text):
                return "omega", f"taxonomy:{primary_type}:omega_evidence_override", [f"taxonomy:{primary_type}", "omega_evidence"]
            if _route_has_broad_legacy_multivitamin_panel(product):
                return (
                    "multi_or_prenatal",
                    "legacy_multivitamin_broad_panel",
                    ["legacy_supplement_type:multivitamin", "broad_multi_panel"],
                )
            return "generic", f"taxonomy:{primary_type}", [f"taxonomy:{primary_type}"]

    if _route_is_omega_class(product, name_text):
        return "omega", "profile_content:omega", ["omega_evidence"]
    if _route_has_broad_legacy_multivitamin_panel(product):
        return (
            "multi_or_prenatal",
            "legacy_multivitamin_broad_panel",
            ["legacy_supplement_type:multivitamin", "broad_multi_panel"],
        )
    return "generic", "generic_safe_default", ["generic_safe_default"]


def _route_is_fiber_digestive_class(product: Dict[str, Any], name_text: str) -> bool:
    primary_type = _primary_type(product)
    if _ROUTE_FIBER_DIGESTIVE_NAME_RE.search(name_text or ""):
        return True

    rows = list(_route_scoring_rows(product))
    digestive_signal_count = 0
    row_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_count += 1
        canonical = _norm(row.get("canonical_id")).replace("-", "_")
        category = _norm(row.get("category"))
        source = " ".join(
            _norm(row.get(key))
            for key in ("name", "standard_name", "standardName", "raw_source_text")
        )
        if canonical in {
            "fiber",
            "psyllium",
            "psyllium_husk",
            "inulin",
            "acacia_fiber",
            "prebiotics",
        }:
            return True
        if category == "fiber" or "psyllium" in source:
            return True
        if canonical in {
            "digestive_enzymes",
            "pepsin",
            "protease",
            "amylase",
            "lipase",
            "bromelain",
            "papain",
        } or "digestive enzyme" in source:
            digestive_signal_count += 1
    return (
        (primary_type == "fiber_digestive" and digestive_signal_count > 0)
        or (row_count > 0 and digestive_signal_count > row_count * 0.5)
    )


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


def _product_standardized_botanical_keys(product: Dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    formulation = _safe_dict(product.get("formulation_data"))
    for item in _safe_list(formulation.get("standardized_botanicals")):
        if not isinstance(item, dict):
            continue
        for key in (item.get("name"), item.get("botanical_id"), item.get("standard_name")):
            slug = _slug(key)
            if slug:
                keys.add(slug)
            norm_key = _norm(key)
            if norm_key:
                keys.add(norm_key)
    return keys


def _botanical_source_evidence(row: Dict[str, Any], product: Optional[Dict[str, Any]] = None) -> tuple[bool, List[str]]:
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
    # standardized_botanicals.json membership is only botanical proof for a
    # GENUINE botanical identity. The file contains non-botanical branded
    # compounds (e.g. Setria glutathione); membership alone must not make a
    # tripeptide/amino-acid a botanical row. Require botanical_ingredients
    # identity or a therapeutic botanical reference.
    genuine_botanical = is_known_botanical(
        row.get("canonical_id"), row.get("name") or row.get("standard_name") or row.get("standardName")
    ) or has_therapeutic_reference(
        row.get("canonical_id"), row.get("name") or row.get("standard_name") or row.get("standardName")
    )
    if genuine_botanical and _norm(row.get("canonical_source_db")) == "standardized_botanicals":
        evidence.append("standardized_botanical_source_db")
    standardized_keys = _product_standardized_botanical_keys(product or {})
    row_keys = {
        _slug(row.get("canonical_id")),
        _slug(row.get("evidence_canonical_id")),
        _slug(row.get("name")),
        _slug(row.get("standardName")),
        _slug(row.get("standard_name")),
        _norm(row.get("canonical_id")),
        _norm(row.get("evidence_canonical_id")),
        _norm(row.get("name")),
        _norm(row.get("standardName")),
        _norm(row.get("standard_name")),
    }
    if genuine_botanical and standardized_keys and any(key and key in standardized_keys for key in row_keys):
        evidence.append("product_standardized_botanical")
    for form in _safe_list(row.get("forms") or raw_taxonomy.get("forms")):
        if not isinstance(form, dict):
            continue
        if _norm(form.get("category")) in _CLASSIFICATION_BOTANICAL_SOURCE_FORM_CATEGORIES:
            evidence.append("botanical_source_form")
            break
    text = _classification_row_text(row).lower()
    if (
        not _CLASSIFICATION_ANIMAL_SOURCE_RE.search(text)
        and any(term in text for term in _CLASSIFICATION_BOTANICAL_SOURCE_TERMS)
    ):
        evidence.append("botanical_source_text")
    return bool(evidence), sorted(set(evidence))


def _ingredient_domain(row: Dict[str, Any], *, botanical_source: bool) -> str:
    canonical = _classification_identity(row)
    dose_class = _norm(row.get("dose_class"))
    unit = _norm(row.get("unit") or row.get("dose_unit"))
    text = _classification_row_text(row)
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    raw_category = _norm(raw_taxonomy.get("category") or row.get("category")).replace("-", "_")

    if dose_class == "probiotic_cfu" or "cfu" in unit:
        return "probiotic_strain"
    if dose_class == "enzyme_activity":
        return "enzyme"
    if canonical in _CLASSIFICATION_DOMAIN_BY_CANONICAL:
        return _CLASSIFICATION_DOMAIN_BY_CANONICAL[canonical]
    if canonical in _CLASSIFICATION_ISOLATED_BOTANICAL_MARKERS:
        return "botanical_marker"
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
    if _CLASSIFICATION_ISOLATED_BOTANICAL_TEXT_RE.search(text):
        return "botanical_marker"
    if _CLASSIFICATION_PROBIOTIC_TEXT_RE.search(text):
        return "probiotic_strain"
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
    botanical_profile_domain = domain == "herb" or (
        domain == "generic_active"
        and canonical not in _CLASSIFICATION_NON_BOTANICAL_GENERIC_CANONICALS
    )
    profile: Dict[str, Dict[str, Any]] = {
        "botanical": {
            "eligible": bool(botanical_source and botanical_profile_domain),
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


_PROFILE_PRIMARY_ROLES = frozenset({"primary", "claim_prominent"})
_PROFILE_BOTANICAL_OWNER_MATERIALITY_FRACTION = 1.0
_PROFILE_BOTANICAL_TITLE_HEAD_MATERIALITY_FRACTION = 0.5
_PROFILE_NONBOTANICAL_BLOCKER_MATERIALITY_FRACTION = 0.5
_PROFILE_TITLE_SEPARATORS = (" with ", " plus ", " and ", " featuring ", " + ", " & ", "+", "&")
# Match the "digest" stem (digest, digest+, digestion, digestive) — a digestive
# enzyme product titled "Digest+" carries digestive intent just like "Digestive".
# Enzyme presence is still required separately, so this never de-botanizes a
# botanical cleanse that merely has "Digestion" in its name.
_PROFILE_ENZYME_TITLE_RE = re.compile(r"\b(enzymes?|digest\w*)\b", re.IGNORECASE)
_PROFILE_NON_BOTANICAL_INTENT_TYPES = frozenset({
    "single_vitamin",
    "single_mineral",
    "vitamin_mineral_combo",
    "multivitamin",
    "b_complex",
    "omega_3",
    "fish_oil",
    "protein_powder",
    "collagen",
    "probiotic",
    "pre_workout",
    "amino_acid",
})


def _row_profile_eligible(row_contract: Dict[str, Any], profile_name: str) -> bool:
    return _safe_dict(_safe_dict(row_contract.get("profile_eligibility")).get(profile_name)).get("eligible") is True


def _profile_title_boundary(title: str) -> int:
    boundary = len(title)
    for sep in _PROFILE_TITLE_SEPARATORS:
        index = title.find(sep)
        if index != -1:
            boundary = min(boundary, index)
    return boundary


def _profile_row_title_pos(row_contract: Dict[str, Any], title: str) -> Optional[int]:
    positions: List[int] = []
    for candidate in _profile_title_candidates(row_contract):
        if not candidate:
            continue
        index = title.find(candidate)
        if index != -1:
            positions.append(index)
    return min(positions) if positions else None


@lru_cache(maxsize=1)
def _botanical_title_alias_index() -> Dict[str, List[str]]:
    """Identity key -> botanical aliases suitable for product-title matching."""
    try:
        raw = json.loads((_DATA_DIR / "botanical_ingredients.json").read_text())
    except Exception:  # pragma: no cover - absence only reduces title matching
        return {}
    index: Dict[str, set[str]] = {}
    for entry in _safe_list(raw.get("botanical_ingredients")):
        if not isinstance(entry, dict):
            continue
        aliases = {
            _norm(entry.get("id")).replace("_", " "),
            _norm(entry.get("standard_name")),
            _norm(entry.get("latin_name")),
        }
        latin = _norm(entry.get("latin_name"))
        if latin and " " in latin:
            aliases.add(latin.split(" ", 1)[0])
        aliases.update(_norm(alias) for alias in _safe_list(entry.get("aliases")))
        aliases = {alias for alias in aliases if alias}
        for key in aliases:
            index.setdefault(key, set()).update(aliases)
    return {key: sorted(values) for key, values in index.items()}


def _profile_title_candidates(row_contract: Dict[str, Any]) -> List[str]:
    candidates = {
        _norm(row_contract.get("canonical_id")).replace("_", " "),
        _norm(row_contract.get("name")),
    }
    alias_index = _botanical_title_alias_index()
    for key in list(candidates):
        candidates.update(alias_index.get(key, []))
    return sorted(candidate for candidate in candidates if candidate)


def _profile_botanical_is_title_head(
    product: Dict[str, Any],
    botanical_contract: Dict[str, Any],
    non_botanical_heroes: List[Dict[str, Any]],
) -> bool:
    title = _norm(product.get("product_name") or product.get("fullName"))
    if not title:
        return False
    boundary = _profile_title_boundary(title)
    botanical_pos = _profile_row_title_pos(botanical_contract, title)
    non_botanical_positions = [
        pos for pos in (_profile_row_title_pos(row, title) for row in non_botanical_heroes)
        if pos is not None
    ]
    botanical_in_head = botanical_pos is not None and botanical_pos < boundary
    non_botanical_in_head = any(pos < boundary for pos in non_botanical_positions)
    if botanical_in_head and not non_botanical_in_head:
        return True
    if non_botanical_in_head and not botanical_in_head:
        return False
    if botanical_pos is not None and non_botanical_positions:
        return botanical_pos < min(non_botanical_positions)
    return False


def _profile_has_enzyme_product_intent(
    product: Dict[str, Any],
    non_botanical_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]],
) -> bool:
    title = str(product.get("product_name") or product.get("fullName") or "")
    primary_type = _primary_type(product)
    if primary_type not in {"fiber_digestive", "digestive_enzyme"} and not _PROFILE_ENZYME_TITLE_RE.search(title):
        return False
    return any(contract.get("ingredient_domain") == "enzyme" for _, contract in non_botanical_pairs)


def _profile_has_title_match(product: Dict[str, Any], contracts: List[Dict[str, Any]]) -> bool:
    title = _norm(product.get("product_name") or product.get("fullName"))
    if not title:
        return False
    return any(_profile_row_title_pos(contract, title) is not None for contract in contracts)


def _profile_has_non_botanical_product_intent(
    product: Dict[str, Any],
    non_botanical_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]],
) -> bool:
    non_botanical_contracts = [contract for _, contract in non_botanical_pairs]
    if _profile_has_title_match(product, non_botanical_contracts):
        return True
    return _primary_type(product) in _PROFILE_NON_BOTANICAL_INTENT_TYPES


def _profile_is_material(primary_mass_mg: float, other_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]]) -> bool:
    max_other_mass = max((_role_mass_mg(row) or 0.0 for row, _ in other_pairs), default=0.0)
    if max_other_mass <= 0:
        return True
    return primary_mass_mg >= (_PROFILE_BOTANICAL_OWNER_MATERIALITY_FRACTION * max_other_mass)


def _profile_is_title_head_material(primary_mass_mg: float, other_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]]) -> bool:
    max_other_mass = max((_role_mass_mg(row) or 0.0 for row, _ in other_pairs), default=0.0)
    if max_other_mass <= 0:
        return True
    return primary_mass_mg >= (_PROFILE_BOTANICAL_TITLE_HEAD_MATERIALITY_FRACTION * max_other_mass)


# --- Phase 2: botanical owner_type model -----------------------------------
# Ownership ("should this product use the botanical adapters?") is SEPARATE from
# row-level botanical source ("does this row have botanical/source properties?").
# A botanical owns the product only when role + materiality + intent + therapeutic
# reference agree. Reference-DB presence is EVIDENCE, not ownership.
_PROFILE_BOTANICAL_OWNER_TYPES = frozenset({
    "therapeutic_botanical", "standardized_botanical", "botanical_blend",
})
# A material non-botanical deliverable in any of these domains blocks a merely
# source/support botanical from owning the product (advisor #4 — expanded beyond
# vitamin/mineral). Materiality is compared in comparable mass units only.
_PROFILE_MATERIAL_NONBOTANICAL_DOMAINS = frozenset({
    "vitamin", "mineral", "amino_acid", "fatty_acid", "omega_epa_dha",
    "omega_parent", "sports_active", "probiotic_strain", "enzyme", "collagen",
})
_PROFILE_DELIVERABLE_ROLES = frozenset({"primary", "claim_prominent", "major"})
_PROFILE_MICRONUTRIENT_DOMAINS = frozenset({"vitamin", "mineral"})
_PROFILE_STANDARDIZED_EVIDENCE = frozenset({
    "standardized_botanical_source_db", "product_standardized_botanical",
})


def _profile_row_ref(contract: Dict[str, Any]) -> str:
    return str(contract.get("row_ref") or contract.get("canonical_id") or contract.get("name") or "")


def _botanical_row_evidence(contract: Dict[str, Any]) -> List[str]:
    ev = _safe_dict(contract.get("botanical_source")).get("evidence")
    return ev if isinstance(ev, list) else []


def _profile_material_blocking_mass(row: Dict[str, Any], botanical_mass_mg: float) -> bool:
    """True when a non-botanical row is material enough to block ownership.

    Only comparable mass units participate. Unknown/NP/activity/CFU units return
    None from _role_mass_mg and therefore cannot win a mass comparison. When the
    botanical mass itself is unknown, do not infer materiality from mass.
    """
    other_mass = _role_mass_mg(row)
    if other_mass is None or botanical_mass_mg <= 0:
        return False
    return other_mass >= (_PROFILE_NONBOTANICAL_BLOCKER_MATERIALITY_FRACTION * botanical_mass_mg)


def _classify_botanical_owner_type(
    product: Dict[str, Any],
    rows: List[Dict[str, Any]],
    row_contracts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Decide whether/why a product is botanical-OWNED.

    Returns {owner_type, owner_reason_code, owner_row_refs, blocking_row_refs,
    support_row_refs}. owner_type in _PROFILE_BOTANICAL_OWNER_TYPES means the
    product should use the botanical adapters; the others mean it should not."""
    pairs = list(zip(rows, row_contracts))
    botanical_pairs = [(r, c) for r, c in pairs if _row_profile_eligible(c, "botanical")]
    if not botanical_pairs:
        return {
            "owner_type": "not_botanical_owner",
            "owner_reason_code": "no_botanical_rows",
            "owner_row_refs": [], "blocking_row_refs": [], "support_row_refs": [],
        }

    primary_row, primary_contract = max(botanical_pairs, key=lambda p: (_role_mass_mg(p[0]) or 0.0))
    botanical_mass = _role_mass_mg(primary_row) or 0.0
    non_botanical_pairs = [(r, c) for r, c in pairs if not _row_profile_eligible(c, "botanical")]
    botanical_is_material = _profile_is_material(botanical_mass, non_botanical_pairs)
    botanical_is_title_head = _profile_botanical_is_title_head(
        product,
        primary_contract,
        [c for _, c in non_botanical_pairs],
    )
    botanical_is_title_head_material = (
        botanical_is_title_head
        and _profile_is_title_head_material(botanical_mass, non_botanical_pairs)
    )
    botanical_is_hero = primary_contract.get("role") in _PROFILE_PRIMARY_ROLES
    non_botanical_heroes = [c for _, c in non_botanical_pairs if c.get("role") in _PROFILE_PRIMARY_ROLES]
    # Material non-botanical deliverables — comparable mass units only (advisor #4).
    material_blockers = [
        c for r, c in non_botanical_pairs
        if c.get("role") in _PROFILE_DELIVERABLE_ROLES
        and c.get("ingredient_domain") in _PROFILE_MATERIAL_NONBOTANICAL_DOMAINS
        and _profile_material_blocking_mass(r, botanical_mass)
    ]
    micronutrient_deliverables = [
        c for _r, c in non_botanical_pairs
        if c.get("role") in _PROFILE_DELIVERABLE_ROLES
        and c.get("ingredient_domain") in _PROFILE_MICRONUTRIENT_DOMAINS
    ]
    botanical_standardized = any(
        e in _PROFILE_STANDARDIZED_EVIDENCE for e in _botanical_row_evidence(primary_contract)
    )
    botanical_has_ref = has_therapeutic_reference(
        primary_contract.get("canonical_id"), primary_contract.get("name")
    )
    owner_refs = [_profile_row_ref(c) for _, c in botanical_pairs]
    blocking_refs = [_profile_row_ref(c) for c in material_blockers]
    support_refs = [_profile_row_ref(c) for _, c in botanical_pairs]

    def refs(contracts: List[Dict[str, Any]]) -> List[str]:
        return [_profile_row_ref(c) for c in contracts]

    def owns(owner_type: str, reason: str, blockers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return {
            "owner_type": owner_type, "owner_reason_code": reason,
            "owner_row_refs": owner_refs, "blocking_row_refs": refs(blockers) if blockers is not None else blocking_refs,
            "support_row_refs": [],
        }

    def not_owner(owner_type: str, reason: str, blockers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return {
            "owner_type": owner_type, "owner_reason_code": reason,
            "owner_row_refs": [], "blocking_row_refs": refs(blockers) if blockers is not None else blocking_refs,
            "support_row_refs": support_refs,
        }

    # Enzyme/digestive product whose botanical is flavor/support -> not owner.
    if _profile_has_enzyme_product_intent(product, non_botanical_pairs):
        return not_owner("phytonutrient_support", "material_nonbotanical_deliverable")

    # Isolated plant-derived markers (resveratrol, lycopene, lutein, etc.) can
    # have botanical-source evidence, but they are not herb/extract owners for
    # botanical dose/formulation adapters. They should score as the isolated
    # active unless paired with a genuine owning herb/extract row.
    if primary_contract.get("ingredient_domain") == "botanical_marker":
        return not_owner("phytonutrient_support", "isolated_botanical_marker")

    # Standardized / branded extract owns when it is materially dominant, or
    # when it is the product title-head and still material enough not to be a
    # token support ingredient. This preserves real Sambucus/elderberry-style
    # products while preventing standardized fruit/veg support rows from owning
    # multivitamins and mixed non-botanical formulas.
    if botanical_standardized and (botanical_is_material or botanical_is_title_head_material):
        return owns("standardized_botanical", "standardized_botanical_owner")

    # Source/carrier guard (legacy-arbiter parity): a botanical that is NOT the
    # marketed primary, in a product whose intent is a non-botanical nutrient,
    # and which the title does not name, is acting as a source/support (e.g.
    # lichen-sourced Vitamin D, acerola in a Vitamin-D+K2 product) -> not owner.
    # This catches mass-dominant carriers even when the carried micronutrient is
    # tiny-mass (so it never registers as a "material blocker").
    if (
        not botanical_is_hero
        and not botanical_has_ref
        and _profile_has_non_botanical_product_intent(product, non_botanical_pairs)
        and not _profile_has_title_match(product, [c for _, c in botanical_pairs])
    ):
        micronutrient_present = any(
            c.get("ingredient_domain") in _PROFILE_MICRONUTRIENT_DOMAINS
            for _, c in non_botanical_pairs
        )
        if micronutrient_present:
            return not_owner("nutrient_source", "nutrient_source_blocks_botanical")
        return not_owner("phytonutrient_support", "non_botanical_product_intent")

    if material_blockers:
        botanical_wins_title = (
            not non_botanical_heroes
            or _profile_botanical_is_title_head(product, primary_contract, non_botanical_heroes)
        )
        if (
            botanical_has_ref
            and botanical_wins_title
            and (botanical_is_material or botanical_is_title_head_material)
        ):
            return owns("therapeutic_botanical", "therapeutic_botanical_owner")
        all_micronutrient = all(
            c.get("ingredient_domain") in _PROFILE_MICRONUTRIENT_DOMAINS for c in material_blockers
        )
        if all_micronutrient and not botanical_has_ref:
            return not_owner("nutrient_source", "nutrient_source_blocks_botanical")
        return not_owner("phytonutrient_support", "material_nonbotanical_deliverable")

    if non_botanical_heroes and not _profile_botanical_is_title_head(product, primary_contract, non_botanical_heroes):
        return not_owner(
            "phytonutrient_support",
            "nonbotanical_title_head_blocks_botanical",
            non_botanical_heroes,
        )

    if micronutrient_deliverables and not botanical_has_ref:
        return not_owner(
            "nutrient_source",
            "nutrient_source_blocks_botanical",
            micronutrient_deliverables,
        )

    # No material non-botanical deliverable competes.
    if botanical_has_ref and (botanical_is_hero or botanical_is_material or botanical_is_title_head_material):
        return owns("therapeutic_botanical", "therapeutic_botanical_owner")
    max_non_botanical_mass = max((_role_mass_mg(r) or 0.0 for r, _ in non_botanical_pairs), default=0.0)
    if max_non_botanical_mass <= botanical_mass and botanical_is_material:
        return owns("botanical_blend", "botanical_blend_owner")
    return not_owner("phytonutrient_support", "phytonutrient_support_only")


def _product_botanical_profile_eligible(
    product: Dict[str, Any],
    rows: List[Dict[str, Any]],
    row_contracts: List[Dict[str, Any]],
) -> bool:
    """Phase 3: botanical ownership is decided by owner_type. The product owns
    the botanical adapters only for a genuine botanical intervention
    (therapeutic / standardized / botanical-dominant blend) — never when it is
    merely a nutrient source or phytonutrient support competing with a material
    non-botanical deliverable. The full reasoning lives in
    ``_classify_botanical_owner_type`` (role + materiality + intent + reference);
    this is the boolean view of it."""
    owner = _classify_botanical_owner_type(product, rows, row_contracts)
    return owner["owner_type"] in _PROFILE_BOTANICAL_OWNER_TYPES


def _product_collagen_profile_eligible(rows: List[Dict[str, Any]], row_contracts: List[Dict[str, Any]]) -> bool:
    pairs = list(zip(rows, row_contracts))
    collagen_pairs = [(row, contract) for row, contract in pairs if _row_profile_eligible(contract, "collagen")]
    if not collagen_pairs:
        return False
    primary_row, _ = max(collagen_pairs, key=lambda pair: (_role_mass_mg(pair[0]) or 0.0))
    collagen_mass = _role_mass_mg(primary_row) or 0.0
    non_collagen_masses = [
        _role_mass_mg(row) or 0.0
        for row, contract in pairs
        if not _row_profile_eligible(contract, "collagen")
    ]
    return max(non_collagen_masses, default=0.0) <= collagen_mass


def _product_level_profile_eligible(
    product: Dict[str, Any],
    rows: List[Dict[str, Any]],
    row_contracts: List[Dict[str, Any]],
    profile_name: str,
    route_module: str,
) -> bool:
    if profile_name in {"omega", "probiotic", "sports"}:
        return route_module == profile_name
    if profile_name in {"botanical", "collagen"} and route_module != "generic":
        return False
    if profile_name == "botanical":
        return _product_botanical_profile_eligible(product, rows, row_contracts)
    if profile_name == "collagen":
        return _product_collagen_profile_eligible(rows, row_contracts)
    return False


def _product_profile_summary(
    product: Dict[str, Any],
    rows: List[Dict[str, Any]],
    row_contracts: List[Dict[str, Any]],
    *,
    route_module: str,
) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for profile_name in ("botanical", "omega", "probiotic", "sports", "collagen"):
        eligible_rows = [
            row for row in row_contracts
            if _row_profile_eligible(row, profile_name)
        ]
        summary[profile_name] = {
            "eligible": _product_level_profile_eligible(
                product,
                rows,
                row_contracts,
                profile_name,
                route_module,
            ),
            "eligible_row_count": len(eligible_rows),
            "evidence": sorted({
                str(e)
                for row in eligible_rows
                for e in _safe_list(_safe_dict(_safe_dict(row.get("profile_eligibility")).get(profile_name)).get("evidence"))
                if str(e)
            }),
        }
    # Phase 3: botanical `eligible` (computed above via _product_level_profile_
    # eligible -> _product_botanical_profile_eligible) is now derived from
    # owner_type. We also surface the full owner_type explanation here.
    summary["botanical"].update(_classify_botanical_owner_type(product, rows, row_contracts))
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
    if route_module is None and classification_origin == "compatibility_derived":
        embedded = _embedded_native_scoring_classification(product)
        if embedded is not None:
            return embedded

    origin = _valid_classification_origin(classification_origin)
    failed = False
    failure_reason: Optional[str] = None
    route_reason = ""
    route_evidence: List[str] = []
    rows: List[Dict[str, Any]] = []
    roles: List[Dict[str, Any]] = []
    route_rows_cache_sentinel = object()
    previous_route_rows_cache: Any = route_rows_cache_sentinel
    route_rows_cache_installed = False

    try:
        input_result = get_scoring_ingredients(product, strict=True)
        rows = list(input_result.rows)
        previous_route_rows_cache = product.get(_ROUTE_SCORING_ROWS_CACHE_KEY, route_rows_cache_sentinel)
        product[_ROUTE_SCORING_ROWS_CACHE_KEY] = rows
        route_rows_cache_installed = True
    except Exception as exc:  # pragma: no cover - defensive totality path
        failed = True
        failure_reason = f"scoring_input_failed:{exc.__class__.__name__}"
        rows = []

    try:
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
    finally:
        if route_rows_cache_installed:
            if previous_route_rows_cache is route_rows_cache_sentinel:
                product.pop(_ROUTE_SCORING_ROWS_CACHE_KEY, None)
            else:
                product[_ROUTE_SCORING_ROWS_CACHE_KEY] = previous_route_rows_cache
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
        botanical_source, botanical_evidence = _botanical_source_evidence(row, product)
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
        "profile_eligibility": _product_profile_summary(
            product,
            rows,
            row_contracts,
            route_module=route_module,
        ),
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
