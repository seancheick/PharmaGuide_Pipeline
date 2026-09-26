#!/usr/bin/env python3
"""Universal Evidence Resolver (Phase 3 Architecture).

Canonical orchestration seam for dietary supplement evidence resolution:
    assessable ingredient
            ↓
    canonical identity
            ↓
    query existing owners (facts only)
            ↓
    compose facts & check applicability
            ↓
    canonical Evidence disposition
            ↓
    existing scorer (points when applicable)

The resolver enforces the fundamental doctrine:
    matched owner != Evidence points

Owners declare the facts they canonically own; the resolver composes those
facts to determine whether an ingredient is resolved by authority, resolved by
reviewed human clinical evidence, research-present but applicability-unestablished,
identity-insufficient, literature-resolution-required (Phase 4 target), or
not efficacy-relevant.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from constants import CLEANER_NON_EFFICACY_ROLES

try:
    from scoring_reference_resolver import rda_ul_reference_entry
except ImportError:
    from scripts.scoring_reference_resolver import rda_ul_reference_entry

_DATA_DIR = Path(__file__).resolve().parent / "data"

_IQM_PATH = _DATA_DIR / "ingredient_quality_map.json"
_RDA_UL_PATH = _DATA_DIR / "rda_optimal_uls.json"
_BACKED_CLINICAL_STUDIES_PATH = _DATA_DIR / "backed_clinical_studies.json"
_CLINICAL_STRAINS_PATH = _DATA_DIR / "clinically_relevant_strains.json"
_BOTANICAL_PATH = _DATA_DIR / "botanical_ingredients.json"
_STANDARDIZED_BOTANICALS_PATH = _DATA_DIR / "standardized_botanicals.json"
_THERAPEUTIC_DOSING_PATH = _DATA_DIR / "rda_therapeutic_dosing.json"
_FORM_VOCAB_PATH = _DATA_DIR / "form_keywords_vocab.json"
_BANNED_PATH = _DATA_DIR / "banned_recalled_ingredients.json"
_HARMFUL_ADDITIVES_PATH = _DATA_DIR / "harmful_additives.json"
_LITERATURE_EVIDENCE_PATH = _DATA_DIR / "literature_evidence_records.json"


class EvidenceDisposition(str, Enum):
    """Canonical Evidence disposition contract."""
    RESOLVED_BY_AUTHORITY = "resolved_by_authority"
    RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE = "resolved_by_reviewed_clinical_evidence"
    RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED = "research_present_applicability_unestablished"
    REVIEWED_NULL_UNFAVORABLE = "reviewed_null_unfavorable"
    NO_QUALIFYING_HUMAN_EVIDENCE = "no_qualifying_human_evidence"
    IDENTITY_INSUFFICIENT = "identity_insufficient"
    LITERATURE_RESOLUTION_REQUIRED = "literature_resolution_required"
    NOT_EFFICACY_RELEVANT = "not_efficacy_relevant"


@dataclass(frozen=True)
class OwnerCapability:
    """Capability declaration for an authoritative evidence owner."""
    owner_id: str
    data_source: str
    facts_owned: Tuple[str, ...]
    capability_description: str


OWNER_CAPABILITY_MAP: Dict[str, OwnerCapability] = {
    "identity_iqm": OwnerCapability(
        owner_id="identity_iqm",
        data_source="data/ingredient_quality_map.json",
        facts_owned=("canonical_id", "standard_name", "category", "is_recognized", "is_synthetic", "form_variants"),
        capability_description="Identity validation, category assignment, and canonical parent normalization",
    ),
    "nutrition_authority": OwnerCapability(
        owner_id="nutrition_authority",
        data_source="data/rda_optimal_uls.json",
        facts_owned=("is_essential_nutrient", "dri_type", "rda_value", "ul_value", "unit", "authority"),
        capability_description="Established nutritional authority for essential dietary vitamins and minerals",
    ),
    "backed_clinical_studies": OwnerCapability(
        owner_id="backed_clinical_studies",
        data_source="data/backed_clinical_studies.json",
        facts_owned=("has_reviewed_studies", "study_count", "highest_study_type", "effect_directions", "pmids", "min_clinical_dose", "max_clinical_dose"),
        capability_description="Reviewed human clinical trials, systematic reviews, and meta-analyses",
    ),
    "probiotic_strain_registry": OwnerCapability(
        owner_id="probiotic_strain_registry",
        data_source="data/clinically_relevant_strains.json",
        facts_owned=("is_probiotic", "has_exact_strain", "strain_id", "has_strain_clinical_trial", "is_strain_stub", "species_level_research_present"),
        capability_description="Probiotic strain registry, exact-strain trials, and species vs strain semantics",
    ),
    "standardized_botanicals": OwnerCapability(
        owner_id="standardized_botanicals",
        data_source="data/botanical_ingredients.json; data/rda_therapeutic_dosing.json",
        facts_owned=("is_botanical", "standardized_extract", "marker_compounds", "therapeutic_min_dose", "therapeutic_max_dose"),
        capability_description="Botanical material standardization, constituent active markers, and clinical dose ranges",
    ),
    "dose_exposure": OwnerCapability(
        owner_id="dose_exposure",
        data_source="scoring_reference_resolver.py; data/rda_optimal_uls.json",
        facts_owned=("reference_family", "label_dose", "label_unit", "dose_adequacy", "meets_clinical_floor", "exceeds_upper_limit"),
        capability_description="Dose adequacy evaluation against clinical benchmarks and upper limits",
    ),
    "form_preparation": OwnerCapability(
        owner_id="form_preparation",
        data_source="data/form_keywords_vocab.json; iqm_form_evidence.py",
        facts_owned=("form_name", "form_category", "bioavailability_grade", "excluded_by_study"),
        capability_description="Chemical salt, chelate, extract form, and bioavailability equivalence",
    ),
    "finished_formula": OwnerCapability(
        owner_id="finished_formula",
        data_source="studied_formulas.py",
        facts_owned=("has_finished_product_trial", "formula_id", "study_type", "pmids"),
        capability_description="Product-level finished commercial formulation RCT evidence",
    ),
    "monograph_claims": OwnerCapability(
        owner_id="monograph_claims",
        data_source="USP; Commission E; Health Canada NHP; EFSA",
        facts_owned=("monograph_status", "authorities", "recognized_indications"),
        capability_description="Official monograph efficacy and traditional use recognitions",
    ),
    "safety_boundaries": OwnerCapability(
        owner_id="safety_boundaries",
        data_source="data/banned_recalled_ingredients.json; data/harmful_additives.json",
        facts_owned=("is_banned", "is_recalled", "is_high_risk", "safety_severity", "disqualifies_evidence"),
        capability_description="Regulatory safety disqualification and toxicological boundaries",
    ),
}


@dataclass
class EvidenceResolution:
    """The canonical resolution for a single ingredient active or row."""
    canonical_id: str
    ingredient_name: str
    matched_owners: List[str]
    disposition: str  # EvidenceDisposition value
    points_eligible: bool  # False if not eligible for points under current evidence
    applicability_status: str  # e.g., applicable, sub_clinical, form_mismatch, species_only
    reason_code: str
    owner_facts: Dict[str, Any] = field(default_factory=dict)
    blocking_reasons: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductEvidenceResolution:
    """The composed Evidence resolution for an entire supplement product."""
    dsld_id: str
    product_name: str
    assessable_ingredients_count: int
    resolutions: List[EvidenceResolution]
    overall_disposition: str
    is_assessment_complete: bool
    unresolved_blockers: List[str]
    owner_contributions: Dict[str, int]


def resolve_omega_evidence_standard(product: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve the reviewed omega purpose record against directed exposure.

    The evidence registry owns the available records and their scores.  The
    shared serving-frequency contract owns the daily interval.  This function
    only joins those facts; it does not award Dose credit or infer EPA/DHA from
    carrier-oil mass.
    """
    from scoring_input_contract import (
        PRENATAL_TITLE_RE,
        epa_dha_amounts_per_serving,
    )
    from serving_frequency import resolve_daily_serving_range

    prod = dict(product or {})
    record = next(
        (entry for entry in _load_backed_studies() if entry.get("id") == "INGR_OMEGA3"),
        None,
    )
    standards = {
        str(item.get("id")): item
        for item in (record or {}).get("purpose_evidence", [])
        if isinstance(item, dict) and item.get("id")
    }
    required = {
        "omega_reviewed_weak",
        "triglyceride_strong",
        "prenatal_dha_intake_authority",
    }
    missing = sorted(required - standards.keys())
    if missing:
        raise ValueError(f"INGR_OMEGA3 purpose evidence is incomplete: {missing}")

    epa_ps, dha_ps, combined_ps = epa_dha_amounts_per_serving(prod)
    total_ps = max(epa_ps + dha_ps, combined_ps)
    servings_min, servings_max, defaulted = resolve_daily_serving_range(prod)
    minimum = total_ps * servings_min if total_ps > 0 else 0.0
    maximum = total_ps * servings_max if total_ps > 0 else 0.0
    dha_minimum = dha_ps * servings_min if dha_ps > 0 else 0.0
    title = " ".join(
        str(prod.get(key) or "")
        for key in ("product_name", "fullName", "brand_name", "brandName")
    )
    prenatal = bool(PRENATAL_TITLE_RE.search(title))

    weak = standards["omega_reviewed_weak"]
    strong = standards["triglyceride_strong"]
    prenatal_intake = standards["prenatal_dha_intake_authority"]
    weak_score = float(weak["pillar_score"])
    weak_minimum = float(weak["minimum_daily_epa_dha_mg"])
    strong_score = float(strong["pillar_score"])
    strong_minimum = float(strong["minimum_daily_epa_dha_mg"])
    graduated_minimum = float(strong["graduated_from_daily_epa_dha_mg"])

    selected = weak
    score = weak_score if minimum >= weak_minimum else 0.0
    # The weak record starts at the lowest exposure represented in its cited
    # trials. A disclosed trace amount cannot inherit that evidence. Defaulted
    # frequency remains explicitly marked but does not itself make a qualifying
    # exposure ineligible. Prenatal intake is handled below by its own floor.
    qualified = bool(minimum >= weak_minimum)
    if prenatal:
        if dha_minimum >= float(prenatal_intake["minimum_daily_dha_mg"]):
            selected = prenatal_intake
            score = float(prenatal_intake["pillar_score"])
        else:
            score = 0.0
    elif minimum >= strong_minimum:
        selected = strong
        score = strong_score
    elif minimum >= graduated_minimum:
        selected = strong
        fraction = (minimum - graduated_minimum) / (strong_minimum - graduated_minimum)
        score = weak_score + fraction * (strong_score - weak_score)
        qualified = True

    if maximum >= strong_minimum > minimum:
        qualified = True

    return {
        "score": round(score, 4),
        "record_id": selected.get("id") if score > 0 else None,
        "record_source_pmids": list(selected.get("source_pmids") or []) if score > 0 else [],
        "minimum_daily_epa_dha_mg": round(minimum, 4),
        "maximum_daily_epa_dha_mg": round(maximum, 4),
        "minimum_daily_dha_mg": round(dha_minimum, 4),
        "servings_defaulted": bool(defaulted),
        "applicability_qualified": qualified,
        "prenatal": prenatal,
        # The reviewed outcome evidence is population-dependent (notably
        # baseline DHA status), which a product label cannot establish.  It is
        # retained in the registry but cannot alter a fixed product-quality
        # score.
        "prenatal_outcome_credit_awarded": False,
    }


def _norm(val: Any) -> str:
    return str(val or "").strip().lower()


def _canonical_text(val: Any) -> str:
    s = _norm(val)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# ============================================================================
# Lazy Loaded Singletons & Indexes
# ============================================================================

@lru_cache(maxsize=1)
def _load_iqm() -> Dict[str, Any]:
    # Required reference data: an unreadable file fails loudly instead of
    # silently resolving every active as if the identity owner were empty.
    raw = json.loads(_IQM_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if k != "_metadata" and isinstance(v, dict)}


@lru_cache(maxsize=1)
def _essential_nutrient_canonicals() -> Set[str]:
    """Authoritative canonical set of essential dietary vitamins and minerals."""
    canonicals = {
        "calcium", "magnesium", "zinc", "iron", "selenium", "copper",
        "manganese", "molybdenum", "chromium", "iodine", "sodium",
        "potassium", "chloride", "phosphorus", "boron", "nickel", "tin",
        "thiamin", "riboflavin", "niacin", "folate", "biotin", "pantothenic_acid",
        "choline", "inositol",
    }
    try:
        from scoring_input_contract import _CLASSIFICATION_MINERAL_CANONICALS
        canonicals.update(_CLASSIFICATION_MINERAL_CANONICALS)
    except ImportError:
        pass
    try:
        from scoring_v4.route_features import B_VITAMIN_CANONICALS
        canonicals.update(B_VITAMIN_CANONICALS)
    except ImportError:
        pass
    return canonicals


def is_essential_dietary_nutrient(canonical: str, name: str = "", iqm_entry: Optional[Dict[str, Any]] = None) -> bool:
    """Return whether an identity represents an essential dietary vitamin or mineral."""
    norm_c = _norm(canonical)
    if norm_c.startswith("vitamin_") or norm_c in _essential_nutrient_canonicals():
        return True
    if iqm_entry:
        cat = _norm(iqm_entry.get("category_enum") or iqm_entry.get("category"))
        if cat in {"vitamins", "minerals"}:
            return True
    return False




@lru_cache(maxsize=1)
def _load_backed_studies() -> Tuple[Dict[str, Any], ...]:
    """Load human clinical studies from backed_clinical_studies.json."""
    raw = json.loads(_BACKED_CLINICAL_STUDIES_PATH.read_text(encoding="utf-8"))
    entries = raw.get("backed_clinical_studies", [])
    return tuple(e for e in entries if isinstance(e, dict))


@lru_cache(maxsize=1)
def _backed_studies_index() -> Dict[str, List[Dict[str, Any]]]:
    """Map canonical IDs, study IDs, names, and aliases to clinical studies."""
    idx: Dict[str, List[Dict[str, Any]]] = {}
    for study in _load_backed_studies():
        keys: Set[str] = set()
        study_id = _norm(study.get("id"))
        if study_id:
            keys.add(study_id)
            if study_id.startswith("ingr_"):
                keys.add(study_id[5:].replace("_", " "))
                keys.add(study_id[5:])
        for field_name in ("canonical_id", "ingredient_canonical_id", "standard_name", "ingredient", "study_name"):
            val = _canonical_text(study.get(field_name))
            if val:
                keys.add(val)
                keys.add(val.replace(" ", "_"))
                keys.add(val.replace("_", " "))
        for alias in study.get("aliases", []) or []:
            val = _canonical_text(alias)
            if val:
                keys.add(val)
                keys.add(val.replace(" ", "_"))
                keys.add(val.replace("_", " "))
        for k in keys:
            if k:
                idx.setdefault(k, []).append(study)
    return idx


@lru_cache(maxsize=1)
def _load_botanical_index() -> Dict[str, Dict[str, Any]]:
    """Index therapeutic dosing botanicals and active markers."""
    idx: Dict[str, Dict[str, Any]] = {}
    raw = json.loads(_THERAPEUTIC_DOSING_PATH.read_text(encoding="utf-8"))
    for entry in raw.get("therapeutic_dosing", []):
        cid = _norm(entry.get("canonical_id") or entry.get("id"))
        if cid:
            idx[cid] = entry
            idx[cid.replace("_", " ")] = entry
            idx[cid.replace(" ", "_")] = entry
        sname = _norm(entry.get("standard_name") or entry.get("name"))
        if sname:
            idx[sname] = entry
            idx[sname.replace("_", " ")] = entry
            idx[sname.replace(" ", "_")] = entry
        for alias in entry.get("aliases", []):
            norm_a = _norm(alias)
            idx[norm_a] = entry
            idx[norm_a.replace("_", " ")] = entry
            idx[norm_a.replace(" ", "_")] = entry
    return idx


@lru_cache(maxsize=1)
def _load_literature_evidence() -> Dict[str, Dict[str, Any]]:
    """Index Phase 4 literature evidence records by canonical_id."""
    idx: Dict[str, Dict[str, Any]] = {}
    raw = json.loads(_LITERATURE_EVIDENCE_PATH.read_text(encoding="utf-8"))
    for entry in raw.get("literature_evidence_records", []):
        cid = _norm(entry.get("canonical_id"))
        if cid:
            idx[cid] = entry
    return idx


@lru_cache(maxsize=1)
def _load_safety_disqualifications() -> Set[str]:
    """Load banned or recalled ingredient IDs."""
    banned: Set[str] = set()
    raw = json.loads(_BANNED_PATH.read_text(encoding="utf-8"))
    for entry in raw.get("ingredients", []):
        status = _norm(entry.get("status"))
        if status in {"banned", "recalled", "high_risk"}:
            cid = _norm(entry.get("canonical_id") or entry.get("id"))
            if cid == "risk_garcinia_cambogia":
                # Evaluated via literature evidence (reviewed null/unfavorable on weight loss)
                continue
            if cid:
                banned.add(cid)
                if cid.upper().startswith("BANNED_") or cid.upper().startswith("ADULTERANT_") or cid.upper().startswith("ADD_"):
                    banned.add(_norm(cid.split("_", 1)[1]))
            sname = _norm(entry.get("standard_name"))
            if sname:
                banned.add(sname)
            for a in entry.get("aliases", []):
                banned.add(_norm(a))
    return banned


# ============================================================================
# Universal Evidence Resolver Core
# ============================================================================

def resolve_evidence_for_canonical(
    canonical_id: str,
    *,
    name: Optional[str] = None,
    dose_value: Optional[float] = None,
    dose_unit: Optional[str] = None,
    matched_form: Optional[str] = None,
    is_excipient: bool = False,
    is_blend_header: bool = False,
    cleaner_row_role: Optional[str] = None,
    source_section: Optional[str] = None,
) -> EvidenceResolution:
    """Resolve evidence for an active ingredient identity independently of a product."""
    row = {
        "canonical_id": canonical_id,
        "name": name or canonical_id.replace("_", " ").title(),
        "amount": dose_value,
        "unit": dose_unit,
        "matched_form": matched_form,
        "is_excipient": is_excipient,
        "is_proprietary_blend": is_blend_header,
        "cleaner_row_role": cleaner_row_role,
        "source_section": source_section,
    }
    return resolve_evidence_for_row(row, product=None)


def resolve_evidence_for_row(
    row: Mapping[str, Any],
    product: Optional[Mapping[str, Any]] = None,
) -> EvidenceResolution:
    """Resolve evidence disposition for an assessable ingredient row."""
    row_dict = dict(row)
    canonical = _norm(row_dict.get("canonical_id"))
    name = str(row_dict.get("name") or row_dict.get("standard_name") or canonical).strip()
    norm_name = _canonical_text(name)
    matched_form = _norm(row_dict.get("matched_form") or row_dict.get("form"))

    matched_owners: List[str] = []
    owner_facts: Dict[str, Any] = {}
    blocking_reasons: List[str] = []

    # 1. Check structural & excipient exclusion -> NOT_EFFICACY_RELEVANT
    cleaner_role = _norm(row_dict.get("cleaner_row_role"))
    if (
        row_dict.get("is_excipient")
        or _norm(row_dict.get("source_section")) == "inactive"
        or cleaner_role in CLEANER_NON_EFFICACY_ROLES
    ):
        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=["safety_boundaries"],
            disposition=EvidenceDisposition.NOT_EFFICACY_RELEVANT.value,
            points_eligible=False,
            applicability_status="excipient_or_inactive",
            reason_code="excipient_not_therapeutic_active",
            owner_facts={"is_excipient": True, "cleaner_row_role": cleaner_role},
        )

    # Special context-aware resolution for silica per Policy Lock (provenance/role decides, never name alone)
    if canonical in {"silica", "silicon"}:
        cleaner_role = _norm(row_dict.get("cleaner_row_role"))
        if (
            cleaner_role in {"inactive", "inactive_excipient", "source_descriptor", "specification_limit"}
            or _norm(row_dict.get("source_section")) == "inactive"
            or row_dict.get("is_excipient")
        ):
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=["safety_boundaries"],
                disposition=EvidenceDisposition.NOT_EFFICACY_RELEVANT.value,
                points_eligible=False,
                applicability_status="inactive_excipient_silica",
                reason_code="excipient_not_therapeutic_active",
                owner_facts={"is_excipient": True},
            )
        # Provenance, not name: an active-panel row is an active silica
        # source. A named, undosed blend child ("organic Bamboo extract" under
        # "Silica 10.5 mg") is that active's source material, never a flow agent.
        active_panel_child = (
            cleaner_role == "nested_display_only"
            and _norm(row_dict.get("source_section")) == "active"
        )
        if cleaner_role == "active_scorable" or active_panel_child or (
            row_dict.get("amount") is not None
            and _as_float(row_dict.get("amount")) is not None
            and _as_float(row_dict.get("amount")) > 0
            and _norm(row_dict.get("source_section")) != "inactive"
        ):
            matched_owners.append("nutrition_authority")
            owner_facts["nutrition_authority"] = {
                "nutrient": "silicon",
                "category": "minerals",
                "is_essential": False,
                "authority": "National Academies DRI (trace mineral, no RDA established)",
            }
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESOLVED_BY_AUTHORITY.value,
                points_eligible=False,
                applicability_status="non_essential_trace_mineral",
                reason_code="trace_mineral_authority_established",
                owner_facts=owner_facts,
            )
        # Ambiguous -> unresolved
        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=["identity_iqm"],
            disposition=EvidenceDisposition.IDENTITY_INSUFFICIENT.value,
            points_eligible=False,
            applicability_status="silica_provenance_ambiguous",
            reason_code="silica_role_ambiguous_requires_label_provenance",
            blocking_reasons=["silica_provenance_ambiguous"],
        )

    if row_dict.get("is_proprietary_blend") or row_dict.get("is_parent_total"):
        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=["identity_iqm"],
            disposition=EvidenceDisposition.IDENTITY_INSUFFICIENT.value,
            points_eligible=False,
            applicability_status="blend_header_undisclosed",
            reason_code="structural_blend_header_cannot_carry_evidence",
            blocking_reasons=["blend_header_lacks_constituent_disclosure"],
        )

    # 2. Check safety boundaries
    banned_set = _load_safety_disqualifications()
    if canonical in banned_set or norm_name in banned_set:
        matched_owners.append("safety_boundaries")
        owner_facts["safety_boundaries"] = {"disqualified": True, "reason": "regulatory_ban_or_recall"}
        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=matched_owners,
            disposition=EvidenceDisposition.NOT_EFFICACY_RELEVANT.value,
            points_eligible=False,
            applicability_status="safety_disqualified",
            reason_code="banned_or_recalled_ingredient",
            owner_facts=owner_facts,
            blocking_reasons=["regulatory_safety_disqualification"],
        )

    # 3. Check Identity & IQM recognition
    iqm = _load_iqm()
    iqm_entry = iqm.get(canonical)
    if iqm_entry:
        matched_owners.append("identity_iqm")
        owner_facts["identity_iqm"] = {
            "is_recognized": True,
            "category": iqm_entry.get("category"),
            "standard_name": iqm_entry.get("standard_name"),
        }
    else:
        # Check if canonical is known or unmapped token
        if not canonical or canonical in {"unmapped", "none", "unknown", "blend_general"}:
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.IDENTITY_INSUFFICIENT.value,
                points_eligible=False,
                applicability_status="unmapped_identity",
                reason_code="canonical_identity_unresolved",
                blocking_reasons=["unresolved_canonical_id"],
            )

    # 4. Check Finished Formula RCT evidence (product-level direct RCT)
    if product:
        try:
            from studied_formulas import formula_clinical_match
            formula = formula_clinical_match(dict(product))
            if formula:
                matched_owners.append("finished_formula")
                owner_facts["finished_formula"] = {
                    "formula_id": formula.get("id"),
                    "study_type": formula.get("study_type"),
                    "pmids": formula.get("published_studies", []),
                }
                return EvidenceResolution(
                    canonical_id=canonical,
                    ingredient_name=name,
                    matched_owners=matched_owners,
                    disposition=EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
                    points_eligible=True,
                    applicability_status="product_level_formula_rct",
                    reason_code="finished_formula_trial_matched",
                    owner_facts=owner_facts,
                )
        except ImportError:
            pass

    # 5. Check Probiotic Strain Registry
    # Check if probiotic identity
    from probiotic_measurements import is_probiotic_source_identity
    is_prob = is_probiotic_source_identity(row_dict)

    if is_prob:
        matched_owners.append("probiotic_strain_registry")
        # Check strain clinical trials vs species research
        # If row has exact strain in name / raw text
        raw_text = str(row_dict.get("raw_source_text") or name)
        from studied_formulas import assess_probiotic_component_disposition
        prob_input = dict(product) if product else {"ingredient_quality_data": {"ingredients": [row_dict]}}
        prob_disp = assess_probiotic_component_disposition(prob_input)
        state = prob_disp.get("disposition_state")
        owner_facts["probiotic_strain_registry"] = prob_disp

        if state == "evaluated_applicable":
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
                points_eligible=True,
                applicability_status="exact_strain_trial_established",
                reason_code="probiotic_exact_strain_verified",
                owner_facts=owner_facts,
            )
        elif state == "native_research_review_incomplete":
            # An identified strain whose identity or clinical review is still
            # open (registry stub, sign-off pending, or a context awaiting
            # clinician review) is not a conclusion. Another strain's points
            # cannot close it.
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value,
                points_eligible=False,
                applicability_status=state,
                reason_code="probiotic_strain_review_incomplete",
                owner_facts=owner_facts,
                blocking_reasons=["probiotic_strain_review_incomplete"],
            )
        elif state == "no_qualifying_human_evidence":
            # Every identified strain's literature review is finished and found
            # no qualifying human evidence (combination-only, uncontrolled or
            # absent research): a reviewed zero.
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value,
                points_eligible=False,
                applicability_status=state,
                reason_code="probiotic_strain_reviewed_no_qualifying_human_evidence",
                owner_facts=owner_facts,
            )
        elif state in {"research_present_applicability_unestablished", "applicability_unestablished"}:
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                points_eligible=False,
                applicability_status=state,
                reason_code="probiotic_species_or_stub_applicability_unestablished",
                owner_facts=owner_facts,
                blocking_reasons=["exact_strain_disclosure_or_trial_lacking"],
            )

    # 6. Check Nutrition Authority (DRI/RDA/AI benchmarks for essential nutrients)
    nutr_entry = rda_ul_reference_entry(canonical_id=canonical, name=name)
    if nutr_entry and is_essential_dietary_nutrient(canonical, name, iqm_entry):
        matched_owners.append("nutrition_authority")
        owner_facts["nutrition_authority"] = {
            "nutrient": nutr_entry.get("id") or nutr_entry.get("standard_name"),
            "category": nutr_entry.get("category"),
            "is_essential": True,
            "ul": nutr_entry.get("ul"),
            "unit": nutr_entry.get("unit"),
        }
        # Established dietary necessity under National Academies DRI
        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=matched_owners,
            disposition=EvidenceDisposition.RESOLVED_BY_AUTHORITY.value,
            points_eligible=False,  # Essential nutrient authority establishes identity/necessity; points earned via dose/generic evidence
            applicability_status="established_essential_nutrient",
            reason_code="dietary_reference_intake_authority_established",
            owner_facts=owner_facts,
        )

    # 7. Check Backed Clinical Studies (Human RCT / Meta-analyses)
    studies_idx = _backed_studies_index()
    iqm_std_name = _canonical_text(iqm_entry.get("standard_name")) if iqm_entry else ""
    matching_studies = (
        studies_idx.get(canonical, [])
        + studies_idx.get(canonical.replace("_", " "), [])
        + studies_idx.get(norm_name, [])
        + studies_idx.get(f"ingr_{canonical}", [])
        + (studies_idx.get(iqm_std_name, []) if iqm_std_name else [])
    )
    # Deduplicate studies by ID
    seen_ids = set()
    deduped_studies = []
    for s in matching_studies:
        sid = s.get("id")
        if sid and sid not in seen_ids:
            seen_ids.add(sid)
            deduped_studies.append(s)

    if deduped_studies:
        matched_owners.append("backed_clinical_studies")
        # Check study types, effect directions, and applicability
        valid_studies = [s for s in deduped_studies if _norm(s.get("study_type")) != "reference"]
        owner_facts["backed_clinical_studies"] = {
            "study_count": len(valid_studies),
            "study_types": list({s.get("study_type") for s in valid_studies}),
            "effect_directions": list({s.get("effect_direction") for s in valid_studies}),
            "pmids": [pmid for s in valid_studies for pmid in s.get("published_studies", [])],
        }

        # Check applicability: dose and form exclusions
        dose_val = _as_float(row_dict.get("amount") or row_dict.get("dose_value"))
        form_val = _canonical_text(matched_form)

        is_form_excluded = False
        is_sub_clinical = False

        for s in valid_studies:
            excluded_forms = [_canonical_text(f) for f in s.get("exclude_aliases", [])]
            if form_val and any(ef in form_val for ef in excluded_forms):
                is_form_excluded = True

            min_dose = _as_float(s.get("min_clinical_dose"))
            if min_dose is not None and dose_val is not None and dose_val < min_dose:
                is_sub_clinical = True

        if is_form_excluded:
            blocking_reasons.append("form_mismatch_with_clinical_trials")
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                points_eligible=False,
                applicability_status="form_mismatch",
                reason_code="clinical_form_mismatch",
                owner_facts=owner_facts,
                blocking_reasons=blocking_reasons,
            )

        if dose_val is None and product is not None:
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                points_eligible=False,
                applicability_status="dose_undisclosed",
                reason_code="constituent_dose_undisclosed_applicability_unestablished",
                owner_facts=owner_facts,
                blocking_reasons=[],
            )

        if is_sub_clinical:
            blocking_reasons.append("dose_below_clinical_trial_minimum")
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                points_eligible=False,
                applicability_status="sub_clinical_dose",
                reason_code="dose_below_studied_clinical_range",
                owner_facts=owner_facts,
                blocking_reasons=blocking_reasons,
            )

        # Has applicable human trials
        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=matched_owners,
            disposition=EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
            points_eligible=True,
            applicability_status="applicable_reviewed_trials",
            reason_code="reviewed_human_clinical_evidence_matched",
            owner_facts=owner_facts,
        )

    # 7b. Check Verified Clinical Evidence Registry (Phase 4 Provenance Fact Registry)
    # The canonical clinical-evidence capability remains ONE owner: backed_clinical_studies.
    # Mere membership in literature_evidence_records.json CANNOT complete evidence without
    # deterministic verification provenance.
    lit_idx = _load_literature_evidence()
    lit_entry = lit_idx.get(canonical) or lit_idx.get(norm_name)
    if lit_entry:
        prov = lit_entry.get("verification_provenance", {})
        is_verified = (
            lit_entry.get("verification_result") == "authoritative_pubmed_verified"
            and prov.get("all_pmids_verified", False) is True
            and not prov.get("retractions_found", False)
        ) or (
            # A food-matrix identity classification makes no literature claim,
            # so PubMed verification has nothing to verify. It may only conclude
            # "not an efficacy active" and may cite no studies.
            lit_entry.get("verification_result") == "identity_classification_no_literature_claim"
            and lit_entry.get("effect_direction") == "not_efficacy_relevant"
            and not lit_entry.get("qualifying_human_studies")
        )
        if not is_verified:
            # Unverified or generated record membership alone MUST NOT complete Evidence
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=["identity_iqm"] if iqm_entry else [],
                disposition=EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value,
                points_eligible=False,
                applicability_status="unverified_literature_record",
                reason_code="unverified_generated_record_cannot_complete_evidence",
                blocking_reasons=["literature_verification_pending"],
            )

        matched_owners.append("backed_clinical_studies")
        owner_facts["literature_evidence"] = {
            "search_date": lit_entry.get("search_date"),
            "search_query": lit_entry.get("search_query"),
            "databases": lit_entry.get("databases_searched"),
            "records_screened": lit_entry.get("records_screened"),
            "effect_direction": lit_entry.get("effect_direction"),
            "pmids": [s.get("pmid") for s in lit_entry.get("qualifying_human_studies", []) if s.get("pmid")],
            "studied_dose": lit_entry.get("studied_dose_exposure"),
            "material_form": lit_entry.get("material_form"),
            "verification_result": lit_entry.get("verification_result"),
        }

        # 7. Check if literature evidence established reviewed null/unfavorable or no studies
        if lit_entry.get("effect_direction") in {"null", "negative", "reviewed_null_unfavorable", "no_qualifying_human_evidence"}:
            studies = lit_entry.get("qualifying_human_studies", [])
            if not studies:
                # Absence of qualifying human studies cannot emit reviewed_null_unfavorable
                return EvidenceResolution(
                    canonical_id=canonical,
                    ingredient_name=name,
                    matched_owners=matched_owners,
                    disposition=EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value,
                    points_eligible=False,
                    applicability_status="no_qualifying_trials_found",
                    reason_code="reproducible_search_found_no_qualifying_human_studies",
                    owner_facts=owner_facts,
                )
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value,
                points_eligible=False,
                applicability_status="reviewed_null_evidence",
                reason_code="literature_reviewed_null_or_unfavorable",
                owner_facts=owner_facts,
            )

        # Check if food matrix / excipient is not efficacy relevant
        if lit_entry.get("effect_direction") == "not_efficacy_relevant":
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.NOT_EFFICACY_RELEVANT.value,
                points_eligible=False,
                applicability_status="food_powder_or_flavor_matrix",
                reason_code="whole_food_matrix_not_efficacy_relevant",
                owner_facts=owner_facts,
            )

        # Check if identity/material is unresolved (identity debt, analytical markers, excipient descriptors)
        if lit_entry.get("effect_direction") in {"identity_material_unresolved", "identity_insufficient"}:
            blocking_reasons.append("identity_material_unresolved")
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.IDENTITY_INSUFFICIENT.value,
                points_eligible=False,
                applicability_status="identity_material_unresolved",
                reason_code="identity_material_unresolved",
                owner_facts=owner_facts,
                blocking_reasons=blocking_reasons,
            )


        # Context-aware material specificity for broad food / carrier identities
        raw_text = _norm(row_dict.get("raw_source_text") or name)
        form_text = _norm(matched_form or "")
        combined_text = f"{raw_text} {form_text}".strip()

        material_form_matched = False
        if canonical == "broccoli":
            if any(k in combined_text for k in ("sprout", "sulforaphane", "glucoraphanin")):
                material_form_matched = True
            else:
                blocking_reasons.append("literature_applicability_unestablished")
                return EvidenceResolution(
                    canonical_id=canonical,
                    ingredient_name=name,
                    matched_owners=matched_owners,
                    disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                    points_eligible=False,
                    applicability_status="crude_whole_food_powder_blocked",
                    reason_code="crude_vegetable_powder_cannot_inherit_purified_extract_trials",
                    owner_facts=owner_facts,
                    blocking_reasons=blocking_reasons,
                )

        if canonical == "pumpkin":
            if any(k in combined_text for k in ("oil", "seed oil", "lipid")):
                material_form_matched = True
            else:
                blocking_reasons.append("literature_applicability_unestablished")
                return EvidenceResolution(
                    canonical_id=canonical,
                    ingredient_name=name,
                    matched_owners=matched_owners,
                    disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                    points_eligible=False,
                    applicability_status="crude_whole_food_powder_blocked",
                    reason_code="crude_seed_powder_cannot_inherit_purified_oil_trials",
                    owner_facts=owner_facts,
                    blocking_reasons=blocking_reasons,
                )

        if canonical in {"orange", "brewers_yeast"}:
            if any(k in combined_text for k in ("extract", "standardized", "bioflavonoid", "hesperidin", "glucan", "polysaccharide")):
                material_form_matched = True
            else:
                return EvidenceResolution(
                    canonical_id=canonical,
                    ingredient_name=name,
                    matched_owners=matched_owners,
                    disposition=EvidenceDisposition.NOT_EFFICACY_RELEVANT.value,
                    points_eligible=False,
                    applicability_status="food_powder_or_flavor_matrix",
                    reason_code="whole_food_matrix_not_efficacy_relevant",
                    owner_facts=owner_facts,
                )

        # Check general applicability decision (only if not already explicitly qualified by material disclosure)
        if not material_form_matched:
            app_dec = str(lit_entry.get("applicability_decision") or "").lower()
            if (
                lit_entry.get("effect_direction") == "applicability_unestablished"
                or "applicability unestablished" in app_dec
                or "prohibited" in app_dec
                or "blocked" in app_dec
            ):
                blocking_reasons.append("literature_applicability_unestablished")
                return EvidenceResolution(
                    canonical_id=canonical,
                    ingredient_name=name,
                    matched_owners=matched_owners,
                    disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                    points_eligible=False,
                    applicability_status="applicability_unestablished",
                    reason_code="literature_applicability_unestablished",
                    owner_facts=owner_facts,
                    blocking_reasons=blocking_reasons,
                )

        # Check dose applicability against studied exposure
        dose_val = _as_float(row_dict.get("amount") or row_dict.get("dose_value"))
        studied_dose = lit_entry.get("studied_dose_exposure")
        if isinstance(studied_dose, dict):
            min_dose = min(studied_dose.get("values", [])) if studied_dose.get("values") else None
        elif isinstance(studied_dose, list) and studied_dose:
            min_dose = min(studied_dose)
        else:
            min_dose = None

        if dose_val is None and product is not None:
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                points_eligible=False,
                applicability_status="dose_undisclosed",
                reason_code="constituent_dose_undisclosed_applicability_unestablished",
                owner_facts=owner_facts,
                blocking_reasons=[],
            )

        if min_dose is not None and dose_val is not None and dose_val < min_dose:
            blocking_reasons.append("dose_below_clinical_trial_minimum")
            return EvidenceResolution(
                canonical_id=canonical,
                ingredient_name=name,
                matched_owners=matched_owners,
                disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
                points_eligible=False,
                applicability_status="sub_clinical_dose",
                reason_code="dose_below_studied_clinical_range",
                owner_facts=owner_facts,
                blocking_reasons=blocking_reasons,
            )

        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=matched_owners,
            disposition=EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
            points_eligible=False,  # Shadow mode: existing scorer alone decides points
            applicability_status="applicable_reviewed_trials",
            reason_code="literature_reviewed_human_clinical_evidence",
            owner_facts=owner_facts,
        )

    # 8. Check Standardized Botanicals / Therapeutic Dosing
    bot_idx = _load_botanical_index()
    bot_entry = bot_idx.get(canonical) or bot_idx.get(norm_name)
    if bot_entry:
        matched_owners.append("standardized_botanicals")
        owner_facts["standardized_botanicals"] = {
            "standard_name": bot_entry.get("standard_name"),
            "is_standardized": bot_entry.get("is_standardized", False),
        }
        # Botanical has therapeutic range but lacks approved human clinical study in DB
        return EvidenceResolution(
            canonical_id=canonical,
            ingredient_name=name,
            matched_owners=matched_owners,
            disposition=EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
            points_eligible=False,
            applicability_status="therapeutic_range_unverified_studies",
            reason_code="botanical_therapeutic_reference_unverified_studies",
            owner_facts=owner_facts,
            blocking_reasons=["clinical_trials_registry_entry_pending"],
        )

    # 9. Recognized Active Identity with No Literature in Database -> LITERATURE_RESOLUTION_REQUIRED
    # This is the exact target for Phase 4 automated literature search!
    return EvidenceResolution(
        canonical_id=canonical,
        ingredient_name=name,
        matched_owners=matched_owners or ["identity_iqm"],
        disposition=EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value,
        points_eligible=False,
        applicability_status="no_reviewed_clinical_studies",
        reason_code="active_identity_requires_literature_search",
        owner_facts=owner_facts,
        blocking_reasons=["literature_search_required_phase4"],
    )


def evidence_owner_canonicals(
    product: Mapping[str, Any],
    *,
    module: Optional[str] = None,
) -> Set[str]:
    """Return the purpose-owning ingredient identities for Evidence.

    Ingredient roles remain owned by ``scoring_input_contract``.  Evidence
    consumes that classification with one precedence rule: explicit route or
    title owners win; otherwise material-major rows own the assessment.  When
    neither signal exists, retain every assessable identity so an opaque blend
    cannot silently discard its ingredients.
    """
    from scoring_input_contract import (
        ROLE_CLAIM_PROMINENT,
        ROLE_MAJOR,
        ROLE_PRIMARY,
        classify_ingredient_roles,
        get_assessable_evidence_ingredients,
        get_scoring_ingredients,
    )

    prod_dict = dict(product or {})
    rows = list(get_scoring_ingredients(prod_dict, strict=True).rows)
    if not rows:
        rows = get_assessable_evidence_ingredients(prod_dict)
    roles = classify_ingredient_roles(prod_dict, module=module, rows=rows)

    def canonicals_for(accepted_roles: Set[str]) -> Set[str]:
        return {
            str(row.get("canonical_id") or "").strip().lower()
            for row, role in zip(rows, roles)
            if role.get("role") in accepted_roles
            and str(row.get("canonical_id") or "").strip()
        }

    explicit = canonicals_for({ROLE_PRIMARY, ROLE_CLAIM_PROMINENT})
    if explicit:
        return explicit
    material = canonicals_for({ROLE_MAJOR})
    if material:
        return material
    return {
        str(row.get("canonical_id") or "").strip().lower()
        for row in rows
        if str(row.get("canonical_id") or "").strip()
    }


def resolve_product_evidence(
    product: Mapping[str, Any],
    *,
    owner_scoped: bool = False,
    module: Optional[str] = None,
) -> ProductEvidenceResolution:
    """Resolve assessable ingredients and compose product-level evidence.

    ``owner_scoped`` limits completeness to the product's purpose-owning
    ingredients.  Adjuncts remain visible in the label and other assessment
    ledgers, but their missing literature cannot override the evidence answer
    for the ingredient the product is actually selling.
    """
    prod_dict = dict(product)
    dsld_id = str(prod_dict.get("dsld_id") or "")
    prod_name = str(prod_dict.get("product_name") or prod_dict.get("name") or "")

    try:
        from scoring_input_contract import get_assessable_evidence_ingredients
        assessable_rows = get_assessable_evidence_ingredients(prod_dict)
    except ImportError:
        # Fallback if scoring_input_contract is not imported
        assessable_rows = []
        for r in prod_dict.get("ingredient_quality_data", {}).get("ingredients", []):
            if r.get("source_section") != "inactive" and not r.get("is_excipient"):
                assessable_rows.append(r)

    if owner_scoped:
        owners = evidence_owner_canonicals(prod_dict, module=module)
        if owners:
            from scoring_input_contract import get_scoring_ingredients
            owner_rows = [
                row
                for row in get_scoring_ingredients(prod_dict, strict=True).rows
                if str(row.get("canonical_id") or "").strip().lower() in owners
            ]
            assessable_rows = owner_rows or [
                row for row in assessable_rows
                if str(row.get("canonical_id") or "").strip().lower() in owners
            ]

    if not assessable_rows:
        return ProductEvidenceResolution(
            dsld_id=dsld_id,
            product_name=prod_name,
            assessable_ingredients_count=0,
            resolutions=[],
            overall_disposition=EvidenceDisposition.NOT_EFFICACY_RELEVANT.value,
            is_assessment_complete=True,
            unresolved_blockers=[],
            owner_contributions={},
        )

    resolutions = [resolve_evidence_for_row(row, prod_dict) for row in assessable_rows]

    # Owner contributions count
    owner_counts: Dict[str, int] = {}
    for res in resolutions:
        for o in res.matched_owners:
            owner_counts[o] = owner_counts.get(o, 0) + 1

    # Composition logic
    dispositions = [r.disposition for r in resolutions]
    all_blockers = [b for r in resolutions for b in r.blocking_reasons]

    # Phase 5 Strict Completeness Contract:
    # A product is marked complete ONLY if ALL assessable evidence-bearing actives
    # have reached terminal evaluated dispositions. Having "some" or "most" ingredients
    # resolved does NOT grant product completeness if an assessable active remains
    # unresolved (identity_insufficient or literature_resolution_required).
    has_identity_insufficient = any(d == EvidenceDisposition.IDENTITY_INSUFFICIENT.value for d in dispositions)
    has_literature_required = any(d == EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value for d in dispositions)
    has_clinical = any(d == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value for d in dispositions)
    has_authority = any(d == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value for d in dispositions)
    has_applicability_unestablished = any(d == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value for d in dispositions)
    has_reviewed_null_unfavorable = any(d == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value for d in dispositions)
    has_no_qualifying = any(d == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value for d in dispositions)

    if has_identity_insufficient:
        overall = EvidenceDisposition.IDENTITY_INSUFFICIENT.value
        complete = False
    elif has_literature_required:
        overall = EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value
        complete = False
    elif has_clinical:
        overall = EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
        complete = True
    elif has_authority:
        overall = EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
        complete = True
    elif has_applicability_unestablished:
        overall = EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
        complete = True
    elif has_reviewed_null_unfavorable:
        overall = EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value
        complete = True
    elif has_no_qualifying:
        overall = EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value
        complete = True
    else:
        overall = EvidenceDisposition.NOT_EFFICACY_RELEVANT.value
        complete = True

    return ProductEvidenceResolution(
        dsld_id=dsld_id,
        product_name=prod_name,
        assessable_ingredients_count=len(assessable_rows),
        resolutions=resolutions,
        overall_disposition=overall,
        is_assessment_complete=complete,
        unresolved_blockers=list(set(all_blockers)),
        owner_contributions=owner_counts,
    )


def resolve_authority_panel_evidence(
    product: Mapping[str, Any],
    *,
    expected_keys: Sequence[str],
    row_key: Callable[[Mapping[str, Any]], str],
    full_score: float = 20.0,
    full_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Score an essential-nutrient panel from the canonical evidence resolver.

    Category modules own which nutrients define their purpose.  This resolver
    owns the evidence decision for each matching label row.  Unrelated actives
    remain visible to the product, but cannot manufacture panel Evidence through
    ingredient count or generic top-N breadth.
    """
    expected = tuple(dict.fromkeys(str(key).strip() for key in expected_keys if str(key).strip()))
    required = int(full_count or len(expected))
    if not expected or required <= 0 or not isinstance(product, Mapping):
        return {
            "score": 0.0,
            "covered_keys": [],
            "expected_keys": list(expected),
            "unresolved_keys": [],
            "resolution_reasons": {},
        }

    from scoring_input_contract import get_assessable_evidence_ingredients

    expected_set = set(expected)
    covered: Set[str] = set()
    seen: Set[str] = set()
    reasons: Dict[str, str] = {}
    for row in get_assessable_evidence_ingredients(dict(product)):
        if not isinstance(row, Mapping):
            continue
        key = str(row_key(row) or "").strip()
        if key not in expected_set:
            continue
        seen.add(key)
        resolution = resolve_evidence_for_row(row, product)
        reasons[key] = resolution.reason_code
        if resolution.disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value:
            covered.add(key)

    unresolved = expected_set - covered
    for key in unresolved - seen:
        reasons[key] = "essential_panel_nutrient_not_disclosed"

    score = min(float(full_score), (len(covered) / required) * float(full_score))
    return {
        "score": round(score, 4),
        "covered_keys": sorted(covered),
        "expected_keys": list(expected),
        "unresolved_keys": sorted(unresolved),
        "resolution_reasons": dict(sorted(reasons.items())),
    }


def _as_float(val: Any) -> Optional[float]:
    try:
        if val is None or isinstance(val, bool):
            return None
        f = float(val)
        return f if (f == f and f != float("inf") and f != float("-inf")) else None
    except (TypeError, ValueError):
        return None
