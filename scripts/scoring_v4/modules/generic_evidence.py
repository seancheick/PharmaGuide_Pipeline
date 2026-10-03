"""v4 generic-module Evidence dimension (P1.3.3).

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 generic rubric, Evidence 20
preserves the Section C multiplicative pipeline:

    study_type × evidence_level × effect_direction × enrollment
    → cap per ingredient → top-N diminishing returns → depth bonus → cap 20

This is a v4-owned implementation. It intentionally does not import the
legacy scorer, but it reads the same enriched `evidence_data.clinical_matches`
contract so before/after score comparisons stay explainable.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from collagen_taxonomy import PEPTIDES_I_III, classify_collagen_subtype_strict
from clinical_applicability import filter_clinical_matches
from scoring_input_contract import (
    primary_mass_competitor_rows,
    get_assessable_evidence_ingredients,
    get_evidence_subject_rows,
    is_lent_blend_mass,
    is_nutrition_fact_declaration as _contract_is_nutrition_fact,
)
from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    daily_serving_multiplier,
    daily_serving_range,
    get_active_ingredients,
    nutrient_delivering_rows,
    delivers_its_nutrient,
    has_usable_individual_dose,
    is_scorable,
)
from scoring_v4.modules.botanical_profile import _mass_mg
from scoring_v4.modules.collagen_profile import is_collagen_product
from scoring_v4.modules.immune_support import (
    immune_support_evidence_cap,
)
from scoring_v4.modules.joint_support import joint_support_evidence_cap


PHASE_MARKER = "P1.3.3_evidence_pipeline"

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_BACKED_CLINICAL_STUDIES_PATH = _DATA_DIR / "backed_clinical_studies.json"

from scoring_v4.quality_score_config import block as _cfg_block

_EM = _cfg_block("evidence_magnitudes", "generic")["generic"]


CAP_TOTAL = _EM["cap_total"]
CAP_PER_INGREDIENT = _EM["cap_per_ingredient"]

STUDY_TYPE_BASE_POINTS: Dict[str, float] = {
    "systematic_review_meta": 6.0,
    "rct_multiple": 5.0,
    "rct_single": 4.0,
    "clinical_strain": 4.0,
    "observational": 2.0,
    "animal_study": 2.0,
    "in_vitro": 1.0,
    "reference": 0.0,
}

EVIDENCE_LEVEL_MULTIPLIERS: Dict[str, float] = {
    "product-human": 1.0,
    "product_human": 1.0,
    "product-rct": 1.0,
    "product_rct": 1.0,
    "product": 1.0,
    "branded-rct": 0.9,
    "branded_rct": 0.9,
    "ingredient-human": 0.9,
    "ingredient_human": 0.9,
    "strain-clinical": 0.65,
    "strain_clinical": 0.65,
    "preclinical": 0.3,
    "reference": 0.0,
}

# ONE owner for what an effect direction is worth: scoring_v4/config/quality_score.json.
# This module used to hard-code the numbers while probiotic_evidence read them from the
# config, and it hard-coded them a SECOND time for the floor path below - three copies of
# one decision. 2026-09-18: null is 0.0 in that one place, so a study that did not show a
# benefit earns no affirmative efficacy credit anywhere.
EFFECT_DIRECTION_MULTIPLIERS: Dict[str, float] = dict(_EM["effect_direction_multipliers"])

ENROLLMENT_ELIGIBLE_STUDY_TYPES = frozenset(
    {"systematic_review_meta", "rct_multiple", "rct_single"}
)
ENROLLMENT_QUALITY_BANDS = tuple(tuple(b) for b in _EM["enrollment_quality_bands"])
ENROLLMENT_DEFAULT_MULTIPLIER = _EM["enrollment_default_multiplier"]

TOP_N_WEIGHTS = tuple(_EM["top_n_weights"])
DEPTH_BONUS_BANDS = tuple(tuple(b) for b in _EM["depth_bonus_bands"])

# Phase 8 — primary-ingredient evidence floor (PROTOTYPE). The top-N additive
# pipeline rewards ingredient COUNT: a focused single clinically-validated
# ingredient (KSM-66) scores ~4.5/20 while two generic minerals score ~11.5/20.
# When the product's PROMINENT active is a strongly-evidenced, positively-
# effective, clinically-dosed ingredient, the dimension earns a floor so quality
# is rewarded independent of count. Keyed on a PROMINENT active (the evidence match
# must link to a dosed label row the shared role owner names as the product's
# purpose), NOT merely the top evidence-points contributor — otherwise a well-studied
# TRACE co-ingredient (calcium in a protein powder) would wrongly float the product.
# Amount adequacy is owned independently by Dose.
PRIMARY_FLOOR_STRONG = _EM["primary_floor_strong"]     # systematic review / multi-RCT, positive, clinical dose
PRIMARY_FLOOR_MODERATE = _EM["primary_floor_moderate"]   # single RCT / clinical strain, positive, clinical dose
# v4.1 branded-RCT tier: a branded clinically-studied extract (Sensoril, KSM-66,
# Meriva/BCM-95 — its OWN brand-specific RCT evidence, not a generic literature
# match) earns a higher floor than a non-branded ingredient at the same study tier.
# 18 (branded + meta/multi-RCT) / 17 (branded + single RCT). 19-20 stays reserved
# for multi-active breadth, so a single extract can be "excellent" but not "perfect".
PRIMARY_FLOOR_BRANDED_STRONG = _EM["primary_floor_branded_strong"]
PRIMARY_FLOOR_BRANDED_MODERATE = _EM["primary_floor_branded_moderate"]
_BRANDED_EVIDENCE_LEVELS = frozenset({"branded-rct", "branded_rct"})
# 3-lane evidence floor (2026-06-06): a broad-consensus SIMPLE ingredient whose
# GENERIC form IS the clinically-validated form earns the elevated (branded-tier)
# floor even without a brand-specific RCT — but only via this explicit allowlist,
# never from automatic generic literature. This keeps a generic ashwagandha BELOW
# KSM-66 (14 vs 18) while letting gold-standard simple ingredients score like the
# reference ingredients they are. Curated, conservative, broad-consensus only:
#   - creatine_monohydrate: monohydrate IS the studied form (sports-routed; here for intent)
#   - psyllium: FDA-recognized soluble-fiber cholesterol/laxation claim; generic husk is studied
#   - vitamin_d: D3 cholecalciferol; overwhelming human evidence, generic form is the studied form
#   - vitamin_b9_folate: folate/folic acid/methylfolate; NTD-prevention consensus
#   - epa / dha: omega-3 actives (omega-routed; here for intent completeness)
# Deliberately EXCLUDED (form-dependent or not consensus-generic): magnesium (oxide
# vs glycinate), iron (form/context-dependent), zinc, generic botanicals.
_CONSENSUS_GOLD_STANDARD = frozenset({
    "creatine_monohydrate",
    "psyllium",
    "vitamin_d",
    "vitamin_b9_folate",
    "epa",
    "dha",
})
_STRONG_STUDY = frozenset({"systematic_review_meta", "rct_multiple"})
_MODERATE_STUDY = frozenset({"rct_single", "clinical_strain"})
# P5 nutrition-authority floor (2026-06): an ESSENTIAL vitamin/mineral with an
# established DRI (RDA/AI) has evidence of *necessity* even without a
# product-specific RCT — "no RCT in our data" must not mean "no evidence of
# usefulness" for a nutrient the body provably requires (copper at evidence 0 was
# the failure). The floor is 10 — deliberately BELOW the 14 non-branded clinical
# floor and 18 branded/consensus tier (established necessity < RCT-proven effect).
# Curated DRI-essentials only (mirrors the multi-panel canonicals); excludes
# UL-only / non-essential bioactives (boron, CoQ10, etc.) so they stay evidence-
# light, and excludes anything not in this set.
NUTRITION_AUTHORITY_FLOOR = _EM["nutrition_authority_floor"]
DRI_ESSENTIAL_NUTRIENTS = frozenset({
    # essential minerals / electrolytes with established RDA or AI
    "copper", "zinc", "selenium", "iodine", "chromium", "molybdenum", "manganese",
    "iron", "calcium", "magnesium", "potassium", "phosphorus", "chloride", "sodium",
    # essential vitamins with established RDA or AI
    "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_e",
    "vitamin_k", "vitamin_k1", "vitamin_k2",
    "vitamin_b1_thiamine", "vitamin_b2_riboflavin", "vitamin_b3_niacin",
    "vitamin_b5_pantothenic", "vitamin_b6_pyridoxine", "vitamin_b7_biotin",
    "vitamin_b9_folate", "vitamin_b12_cobalamin", "choline",
})
# Effect-strength weight on the primary floor. It IS the pipeline's multiplier map, not a
# copy of it: a direction that earns no affirmative credit in the pipeline may not anchor a
# floor either. Directions worth 0 (null, negative) are skipped by the caller.
_EFFECT_FLOOR_MULTIPLIER = EFFECT_DIRECTION_MULTIPLIERS
# Prototype toggle (Phase 8 spike). Set ENABLED=False for the no-floor baseline.
# The floor is gated on the strongly-evidenced ingredient being PROMINENT
# (evidence_resolver.evidence_prominent_row_keys, from the shared role owner), so it
# rewards a product whose PRIMARY ingredient is well-studied (KSM-66, Niacin) and never
# floats a product on a well-studied TRACE co-ingredient (calcium in a protein
# powder) — the failure the focus-gate benchmark surfaced.
PRIMARY_FLOOR_ENABLED = True
# NIH ODS/FNB conversion for Vitamin D label quantities: 1 mcg = 40 IU.
# This is intentionally scoped to evidence matching. Other IU nutrients have
# different, sometimes form-dependent conversions and must remain unresolved.
_VITAMIN_D_IU_PER_MCG = 40.0
_VITAMIN_D_EVIDENCE_KEYS = frozenset(
    {"vitamin d", "vitamin d3", "cholecalciferol"}
)

_RECOVERED_COLLAGEN_PEPTIDES_MATCH = {
    "id": "RECOVERED_COLLAGEN_PEPTIDES_V1",
    "ingredient": "collagen",
    "standard_name": "Collagen",
    "study_type": "systematic_review_meta",
    "evidence_level": "ingredient-human",
    "effect_direction": "positive_strong",
    "total_enrollment": 250,
    "published_studies_count": 26,
    "min_clinical_dose": 2500,
    "max_studied_clinical_dose": 20000,
    "dose_unit": "mg",
    "evidence_origin": "scoring_contract_recovery",
    "source_data": "backed_clinical_studies:INGR_COLLAGEN_PEPTIDES",
}

_MODULE_OWNED_EVIDENCE_CANONICALS = frozenset({
    # These are handled by purpose-built profile/module evidence paths. Generic
    # ingredient-human recovery must not borrow their entries as a fallback.
    "collagen",
    "dha",
    "epa",
    "epa_dha",
    "fish_oil",
    "omega_3",
    "probiotics",
    "probiotic_unspecified",
    "prebiotics",
})


def score_evidence(product: Dict[str, Any], *, apply_primary_floor: bool = False,
                   accepted_matches: Optional[List[Dict[str, Any]]] = None,
                   owner_scoped: bool = False) -> Dict[str, Any]:
    """Compute the generic-module Evidence dimension.

    Returns a dimension payload compatible with
    `GenericModuleResult.dimensions["evidence"]`.

    `apply_primary_floor`: the Phase-8 primary-ingredient floor is opt-in per
    caller. The generic, sports and fiber modules pass True (with
    `owner_scoped`); omega / probiotic / multi reuse this scorer as a
    sub-component with their own evidence logic and do not inherit the floor.
    """
    if not isinstance(product, dict):
        product = {}

    matches, recovered_matches = resolved_clinical_matches(
        product,
        owner_scoped=owner_scoped,
    )
    if accepted_matches is not None:
        # A category may narrow the shared applicability result, never add a
        # match or bypass clinical_applicability's restrictions.
        accepted_ids = {_entry_id(entry) for entry in accepted_matches}
        matches = [entry for entry in matches if _entry_id(entry) in accepted_ids]
        recovered_matches = [entry for entry in recovered_matches if _entry_id(entry) in accepted_ids]
    from evidence_resolver import evidence_owner_canonicals, _evidence_claim_purposes, _evidence_entry_purposes
    claim_purposes = _evidence_claim_purposes(product) if owner_scoped else {}
    owner_canonicals = (
        evidence_owner_canonicals(product)
        if owner_scoped
        else set()
    )
    active_canonical_index = _active_canonical_index(product)
    ingredient_points: Dict[str, float] = defaultdict(float)
    matched_entry_ids: set[str] = set()
    scoped_matches: List[Dict[str, Any]] = []
    scoped_recovered_matches: List[Dict[str, Any]] = []
    flags: List[str] = []
    if owner_scoped:
        from scoring_input_contract import classify_ingredient_roles
        for role in classify_ingredient_roles(product):
            if str(role.get("role_reason", "")).startswith("named_in_label_function_claim:"):
                _append_once(flags, "EXPLICIT_LABEL_PURPOSE_OWNER:" + str(role["canonical_id"]) + ":" + role["role_reason"].split(":", 1)[1])
    sub_clinical_canonicals: set[str] = set()  # compatibility metadata; Dose owns this assessment

    for entry in matches:
        if not isinstance(entry, dict):
            continue
        matched_owner = _matched_active_canonical(
            entry,
            active_canonical_index,
            use_structured_identity=owner_scoped,
            owner_canonicals=owner_canonicals if owner_scoped else None,
        )
        if owner_canonicals and matched_owner not in owner_canonicals:
            continue
        if matched_owner in claim_purposes and not (claim_purposes[matched_owner] & _evidence_entry_purposes(entry)):
            _append_once(flags, "LABEL_PURPOSE_EVIDENCE_MISMATCH:" + str(matched_owner))
            continue

        entry_id = _entry_id(entry)
        if entry_id in matched_entry_ids:
            continue
        matched_entry_ids.add(entry_id)
        scoped_matches.append(entry)
        if any(_entry_id(recovered) == entry_id for recovered in recovered_matches):
            scoped_recovered_matches.append(entry)

        raw = _entry_raw_points(entry)
        if raw <= 0:
            continue

        marker_confidence = entry.get("marker_confidence_scale")
        if marker_confidence is not None:
            scale = _as_float(marker_confidence, None)
            if scale is not None:
                raw *= scale

        canonical = (
            matched_owner
            if owner_scoped and matched_owner
            else _canonical_from_entry(entry)
        )
        if canonical:
            ingredient_points[canonical] += raw

    capped_scores = sorted(
        (min(CAP_PER_INGREDIENT, pts) for pts in ingredient_points.values()),
        reverse=True,
    )

    pipeline_total = 0.0
    for idx, points in enumerate(capped_scores):
        if idx >= len(TOP_N_WEIGHTS):
            break
        pipeline_total += points * TOP_N_WEIGHTS[idx]

    depth_bonus = _depth_bonus(scoped_matches)

    # Phase 8 — primary-ingredient evidence floor. A strongly & positively
    # evidenced match on a prominent row (excluding sub-clinical) anchors a
    # floor, so a focused premium ingredient isn't out-scored by ingredient
    # count. See _primary_mass_floor.
    primary_floor = 0.0
    floor_canonical: Optional[str] = None
    nutrition_authority_canonical: Optional[str] = None
    if apply_primary_floor and PRIMARY_FLOOR_ENABLED:
        from evidence_resolver import evidence_prominent_row_keys
        prominent = evidence_prominent_row_keys(product)
        primary_floor, floor_canonical = _primary_mass_floor(
            product, scoped_matches, prominent=prominent
        )
        # P5: DRI-essential nutrient authority floor. An essential vitamin/mineral
        # with established RDA/AI has evidence of necessity even without a strong
        # RCT match. Floor (never cap) — it only lifts, never lowers the clinical
        # floor above it (e.g. a consensus/branded 18 stays 18).
        explicit_purpose_canonicals = {canonical for _, canonical in prominent}
        if not explicit_purpose_canonicals:
            # A label with one assessable active still has an unambiguous
            # Evidence subject even when the shared role owner has no title or
            # claim signal to mark prominent.  Multiple active identities stay
            # unresolved here: Evidence must not recreate the removed
            # heaviest-mass fallback to choose among them.
            subject_canonicals = {
                str(row.get("canonical_id") or "").strip().lower()
                for row in _competing_active_rows(product)
                if isinstance(row, dict)
                and str(row.get("canonical_id") or "").strip()
                and not is_lent_blend_mass(row)
            }
            if len(subject_canonicals) == 1:
                explicit_purpose_canonicals = subject_canonicals
        auth_canon = _purpose_essential_canonical(
            product,
            owner_canonicals=explicit_purpose_canonicals if explicit_purpose_canonicals else set(),
        )
        if (auth_canon and (not owner_scoped or auth_canon in owner_canonicals)
                and primary_floor < NUTRITION_AUTHORITY_FLOOR):
            primary_floor = NUTRITION_AUTHORITY_FLOOR
            nutrition_authority_canonical = auth_canon
            if not floor_canonical:
                floor_canonical = auth_canon

    total = _clamp(0.0, CAP_TOTAL, max(pipeline_total + depth_bonus, primary_floor))
    immune_cap = immune_support_evidence_cap(product)
    immune_cap_applied = immune_cap is not None and total > immune_cap
    if immune_cap_applied and immune_cap is not None:
        total = immune_cap
    joint_cap = joint_support_evidence_cap(product)
    joint_cap_applied = joint_cap is not None and total > joint_cap
    if joint_cap_applied:
        total = joint_cap

    listed_entries = [
        entry
        for entry in _safe_list(
            _safe_dict(product.get("evidence_data")).get("clinical_matches")
        )
        if isinstance(entry, dict)
    ]
    listed_ids = {
        _entry_id(entry)
        for entry in listed_entries
        if not owner_canonicals
        or _matched_active_canonical(
            entry,
            active_canonical_index,
            use_structured_identity=owner_scoped,
            owner_canonicals=owner_canonicals if owner_scoped else None,
        ) in owner_canonicals
    } | {_entry_id(entry) for entry in scoped_matches}
    from studied_formulas import assess_probiotic_component_disposition
    probiotic_component_evidence = assess_probiotic_component_disposition(product)
    primary_floor_decisive = bool(primary_floor > pipeline_total + depth_bonus)
    evidence_result_state = _evidence_result_state(
        product, total, listed_ids, scoped_matches, probiotic_disposition=probiotic_component_evidence,
        dose_gated=bool(sub_clinical_canonicals), owner_scoped=owner_scoped,
        authority_floor_decisive=bool(
            nutrition_authority_canonical and primary_floor_decisive
        ),
    )

    metadata = {
        "phase": PHASE_MARKER,
        "ingredient_points": {k: round(v, 4) for k, v in sorted(ingredient_points.items())},
        "matched_entries": len(matched_entry_ids),
        "top_n_applied": min(len(capped_scores), len(TOP_N_WEIGHTS)),
        "sub_clinical_canonicals": sorted(sub_clinical_canonicals),
        "recovered_matches": [
            _entry_id(entry)
            for entry in scoped_recovered_matches
        ],
        "evidence_result_state": evidence_result_state,
        "flags": flags,
    }
    if owner_scoped:
        metadata["evidence_owner_canonicals"] = sorted(owner_canonicals)

    components = {
        "clinical_evidence_pipeline": round(pipeline_total, 4),
        "depth_bonus": round(depth_bonus, 4),
    }
    if primary_floor > 0.0:
        components["primary_evidence_floor"] = round(primary_floor, 4)
    if immune_cap_applied and immune_cap is not None:
        components["immune_support_evidence_cap"] = round(immune_cap, 4)
    if joint_cap_applied:
        components["joint_support_evidence_cap"] = round(joint_cap, 4)

    return {
        "score": round(total, 4),
        "max": CAP_TOTAL,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            **metadata,
            "primary_evidence_floor": round(primary_floor, 4),
            "primary_evidence_floor_canonical": floor_canonical,
            # A floor that was COMPUTED is not a floor that DROVE the score.
            # total = max(pipeline + depth, floor), so the floor only decides the
            # result when it strictly exceeds the pipeline; equality means the
            # pipeline already earned that number on its own. The explanation
            # owner reads this instead of re-deriving the comparison.
            "primary_evidence_floor_decisive": primary_floor_decisive,
            # Compatibility fields remain explicit so old clients distinguish
            # a deliberately retired proxy from missing metadata. Ingredient
            # presence or dose can never manufacture Evidence credit.
            "immune_support_evidence_floor_applied": False,
            "immune_support_evidence_floor": None,
            "immune_support_evidence_cap_applied": immune_cap_applied,
            "immune_support_evidence_cap": immune_cap,
            "joint_support_evidence_cap_applied": joint_cap_applied,
            "joint_support_evidence_cap": round(joint_cap, 4) if joint_cap is not None else None,
            "nutrition_authority_floor_applied": nutrition_authority_canonical is not None,
            "nutrition_authority_canonical": nutrition_authority_canonical,
            "probiotic_component_evidence": (
                probiotic_component_evidence
                if (probiotic_component_evidence and probiotic_component_evidence.get("has_probiotic_component"))
                else None
            ),
            "evidence_result_state": evidence_result_state,
            "flags": flags,
        },
    }


def _is_nutrition_fact_declaration(row: Dict[str, Any]) -> bool:
    """Return whether a row is classified by canonical label/row-role owner as a Nutrition Facts declaration."""
    return _contract_is_nutrition_fact(row)


def _assessable_active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return ingredients eligible to be assessed for clinical evidence.

    Consumes the canonical contract from scoring_input_contract.get_assessable_evidence_ingredients.
    """
    if not isinstance(product, dict):
        return []
    return get_assessable_evidence_ingredients(product)


def evidence_completeness_gap(
    product: Dict[str, Any],
    prod_res: Any = None,
    *,
    owner_scoped: bool = False,
) -> Optional[str]:
    """The coverage-gap state when any assessable active is still non-terminal.

    Points are an output of assessment, never proof it finished. Every Evidence
    module asks this before it may report a conclusion; None means complete.
    """
    from evidence_resolver import resolve_product_evidence, EvidenceDisposition
    prod_res = prod_res or resolve_product_evidence(product, owner_scoped=owner_scoped)
    if prod_res.is_assessment_complete:
        return None
    if prod_res.overall_disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value:
        return "identity_material_unresolved"
    if "probiotic_strain_review_incomplete" in prod_res.unresolved_blockers:
        return "native_research_review_incomplete"
    return "clinical_review_not_covered"


def _evidence_result_state(
    product: Dict[str, Any],
    total: float,
    listed_ids: set[str],
    accepted: List[Dict[str, Any]],
    probiotic_disposition: Optional[Dict[str, Any]] = None,
    dose_gated: bool = False,
    owner_scoped: bool = False,
    authority_floor_decisive: bool = False,
) -> str:
    """Why Evidence landed where it did, from the matches that were scored.

    Canonical Phase 5 contract: consumes resolve_product_evidence to determine
    whether all assessable evidence-bearing ingredients have reached terminal
    evaluated dispositions. Points are an output of assessment, never proof
    that assessment occurred.
    """
    # No fallback: a resolver failure must fail loudly, never silently let
    # points stand in for a finished assessment.
    from evidence_resolver import resolve_product_evidence, EvidenceDisposition
    prod_res = resolve_product_evidence(product, owner_scoped=owner_scoped)
    gap = evidence_completeness_gap(product, prod_res, owner_scoped=owner_scoped)

    if total > 0:
        # A product with any assessable active still non-terminal is incomplete
        # even when another active's reviewed evidence already earned points.
        if gap:
            return gap
        # The state names the evidence source that actually set the score. A
        # nutrition-authority floor can be decisive even when a secondary
        # component has separate research details; those details remain on the
        # ingredient and cannot replace the product headline owner.
        if authority_floor_decisive:
            return "evaluated_authority"
        return "evaluated_applicable"
    if not _assessable_active_ingredients(product):
        return "no_assessable_actives"

    # Incomplete assessment: an assessable active is still open. Checked before
    # any conclusion, the probiotic one included.
    if gap:
        return gap

    # Probiotic disposition takes precedence for probiotic products
    if probiotic_disposition and probiotic_disposition.get("has_probiotic_component"):
        # Result-state ownership is narrower than the ingredient-detail view.
        # A secondary probiotic component retains its disposition in component
        # metadata and ingredient resolutions, but it cannot replace a
        # completed authority disposition earned by the product's headline
        # owner. Resolve that owner through the existing structured identity
        # seam without changing the score or filtering the detail payload.
        headline_res = (
            prod_res
            if owner_scoped
            else resolve_product_evidence(product, owner_scoped=True)
        )
        probiotic_owns_headline = any(
            "probiotic_strain_registry" in resolution.matched_owners
            for resolution in headline_res.resolutions
        )
        if (
            not probiotic_owns_headline
            and headline_res.overall_disposition
            == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
        ):
            return "evaluated_authority"
        prob_state = probiotic_disposition.get("disposition_state")
        if prob_state:
            return str(prob_state)

    # Reviewed research exists but its trials ran at doses this label never
    # reaches: a finished conclusion that the research does not apply here.
    if dose_gated:
        return "applicability_unestablished"

    # Evaluated matches on record take precedence when present
    if accepted:
        directions = [_norm_text(entry.get("effect_direction")) for entry in accepted]
        if "negative" in directions:
            return "evaluated_unfavorable"
        if directions and all(direction == "null" for direction in directions):
            return "evaluated_null"
        return "no_qualifying_human_evidence"

    if listed_ids:
        return "applicability_unestablished"

    # No listed clinical matches on record: the (complete) resolver decides.
    return result_state_for_disposition(prod_res.overall_disposition)


def result_state_for_disposition(disp: Optional[str]) -> str:
    """The Evidence result state a composed, complete disposition establishes."""
    from evidence_resolver import EvidenceDisposition
    if disp == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value:
        return "evaluated_authority"
    if disp == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value:
        return "evaluated_null"
    if disp == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value:
        return "no_qualifying_human_evidence"
    if disp in {
        EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
        EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
    }:
        return "applicability_unestablished"
    if disp == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value:
        return "no_assessable_actives"

    return "clinical_review_not_covered"


def authority_panel_result_state(product: Dict[str, Any], authority: Dict[str, Any]) -> str:
    """Result state of an essential-nutrient panel (multi/prenatal, B-complex).

    An open panel row keeps its coverage-gap state even when other nutrients
    earned points. Authority coverage is ``evaluated_authority``. Zero coverage
    is read from what the panel rows did establish, never as a reviewed null:
    no panel nutrient on the label is an uncovered review, not a conclusion.
    """
    panel = authority.get("panel_resolution")
    gap = evidence_completeness_gap(product, panel) if panel is not None else None
    if gap:
        return gap
    if authority.get("covered_keys"):
        return "evaluated_authority"
    if panel is None or not panel.resolutions:
        if not _assessable_active_ingredients(product):
            return "no_assessable_actives"
        return "clinical_review_not_covered"
    return result_state_for_disposition(panel.overall_disposition)


def resolved_clinical_matches(
    product: Dict[str, Any],
    *,
    owner_scoped: bool = False,
    assess_amount: bool = True,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return the exact reviewed evidence rows consumed by v4 scoring.

    Readiness and score math must not maintain separate matching rules.  This
    public seam resolves enrichment-owned clinical matches plus the scorer's
    deliberately narrow contract recoveries once, returning
    ``(all_matches, recovered_matches)`` for provenance.
    """
    product = product if isinstance(product, dict) else {}
    matches = [
        entry
        for entry in _safe_list(
            _safe_dict(product.get("evidence_data")).get("clinical_matches")
        )
        if isinstance(entry, dict)
    ]
    recovered_matches = _recover_contract_evidence_matches(
        product,
        matches,
        owner_scoped=owner_scoped,
    )
    if recovered_matches:
        recovered_ids = {_entry_id(entry) for entry in recovered_matches}
        matches = [
            entry for entry in matches
            if _entry_id(entry) not in recovered_ids
        ]
        matches.extend(recovered_matches)
    matches, _ = filter_clinical_matches(product, matches, assess_amount=assess_amount)
    from studied_formulas import formula_clinical_match, formula_identity_clinical_match
    formula = (formula_clinical_match(product) if assess_amount
               else formula_identity_clinical_match(product))
    if formula:
        matches = [entry for entry in matches if _entry_id(entry) != formula["id"]]
        matches.append(formula)
    accepted_ids = {_entry_id(entry) for entry in matches}
    return matches, [entry for entry in recovered_matches if _entry_id(entry) in accepted_ids]


def _recover_contract_evidence_matches(
    product: Dict[str, Any],
    matches: List[Any],
    *,
    owner_scoped: bool = False,
) -> List[Dict[str, Any]]:
    """Recover evidence when the scoring input contract has a clear primary
    identity but enrichment failed to copy the corresponding clinical match.

    Keep this deliberately narrow. It recovers verified evidence only when the
    scoring contract has already produced a dose-bearing primary row and the row
    has an exact branded/product-level identity in backed_clinical_studies.json.
    Token collagen add-ons stay excluded by is_collagen_product().
    """
    from evidence_resolver import evidence_prominent_row_keys

    recovered: List[Dict[str, Any]] = []
    recovered_ids: set[str] = set()
    # Owner-scoped callers read the shared role owner; the others keep the
    # previous rules (see _recover_verified_primary_ingredient_matches).
    prominent = evidence_prominent_row_keys(product) if owner_scoped else None

    peptide_row = _collagen_peptide_recovery_row(product, prominent=prominent)
    if peptide_row is not None and not _recovery_source_ref(peptide_row):
        # Legacy inputs may lack source refs. Their exact name is usable only
        # when no other dose-bearing row contributes to that lookup key.
        term = _canonical_text(peptide_row.get("name") or peptide_row.get("standard_name"))
        if not term or any(
            row is not peptide_row
            and term in {_canonical_text(row.get(key)) for key in (
                "standard_name", "name", "raw_source_text", "canonical_id",
            )}
            for row in nutrient_delivering_rows(product)
        ):
            peptide_row = None
    if (
        peptide_row is not None
        and not _has_match_for_identity(matches, "collagen")
        and is_collagen_product(product)
    ):
        entry = dict(_RECOVERED_COLLAGEN_PEPTIDES_MATCH)
        entry["matched_term"] = peptide_row.get("name") or peptide_row.get("standard_name")
        entry["matched_canonical_id"] = peptide_row.get("canonical_id")
        _stamp_recovery_source_ref(entry, peptide_row)
        if entry.get("matched_source_row_refs"):
            # A label can declare the same preparation as a protein source
            # and as an active. Keep both determinations linked, without
            # borrowing from a different preparation or summing declarations.
            name = _canonical_text(entry["matched_term"])
            for row in nutrient_delivering_rows(product):
                ref = _recovery_source_ref(row)
                if (ref and _is_collagen_peptide_row(row)
                    and not is_lent_blend_mass(row)
                    and _canonical_text(row.get("name") or row.get("standard_name")) == name
                    and ref not in entry["matched_source_row_refs"]):
                    entry["matched_source_row_refs"].append(ref)
        recovered.append(entry)
        recovered_ids.add(_RECOVERED_COLLAGEN_PEPTIDES_MATCH["id"])

    for entry in _recover_verified_product_level_matches(product, matches):
        entry_id = _entry_id(entry)
        if entry_id and entry_id not in recovered_ids:
            recovered.append(entry)
            recovered_ids.add(entry_id)

    for entry in _recover_verified_primary_ingredient_matches(
        product,
        matches,
        allow_with_existing_matches=owner_scoped,
        prominent=prominent,
    ):
        entry_id = _entry_id(entry)
        if entry_id and entry_id not in recovered_ids:
            recovered.append(entry)
            recovered_ids.add(entry_id)

    return recovered


def _recover_verified_product_level_matches(
    product: Dict[str, Any],
    matches: List[Any],
) -> List[Dict[str, Any]]:
    existing_ids = {
        _entry_id(entry)
        for entry in matches
        if isinstance(entry, dict)
    }
    recovered: List[Dict[str, Any]] = []
    for row in nutrient_delivering_rows(product):
        if not isinstance(row, dict):
            continue
        if (row.get("evidence_type") or "") != "blend_anchor_mass":
            continue
        row_text = _row_identity_text(product, row)
        if not row_text:
            continue
        for entry in _verified_product_level_evidence_entries():
            entry_id = _entry_id(entry)
            if entry_id in existing_ids:
                continue
            if not _verified_product_entry_matches_text(entry, row_text):
                continue
            recovered_entry = dict(entry)
            recovered_entry["evidence_origin"] = "scoring_contract_recovery"
            recovered_entry["source_data"] = f"backed_clinical_studies:{entry_id}"
            # Link the recovered study back to the exact mass-bearing row so
            # the primary-floor gate can prove this is not trace evidence.
            recovered_entry["matched_term"] = row.get("name") or row.get("standard_name")
            recovered_entry["matched_canonical_id"] = row.get("canonical_id")
            _stamp_recovery_source_ref(recovered_entry, row)
            recovered.append(recovered_entry)
            existing_ids.add(entry_id)
    return recovered


def _recovery_source_ref(row: Dict[str, Any]) -> str:
    """Use the same reference validity for recovery selection and stamping."""
    return str(row.get("raw_source_path") or row.get("source_row_ref") or "").strip()


def _stamp_recovery_source_ref(entry: Dict[str, Any], row: Dict[str, Any]) -> None:
    """Bind a scoring-contract recovery to the exact row it was recovered from.

    Source-required applicability scopes evaluate only the referenced source
    row; without the reference every recovery is rejected as unresolved even
    when the row's own label satisfies the scope.
    """
    ref = _recovery_source_ref(row)
    if ref:
        entry["matched_source_row_refs"] = [ref]


def _recover_verified_primary_ingredient_matches(
    product: Dict[str, Any],
    matches: List[Any],
    *,
    allow_with_existing_matches: bool = False,
    prominent: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """Recover exact ingredient-human evidence for a prominent dosed active.

    This closes the NAC-style contract gap: the cleaner/scoring contract has a
    dose-bearing, exact canonical active row, backed_clinical_studies has a
    PubMed-verified ingredient-human entry, but enrichment omitted
    evidence_data.clinical_matches. Keep the recovery intentionally stricter
    than label text matching:

    - only verified ingredient-human entries with structured references;
    - only structured identity equality (canonical_id/standard_name/alias), no
      fuzzy substring matching;
    - owner-scoped callers (generic, sports, fiber Evidence): only a row the
      shared role owner names as the product's purpose
      (``evidence_resolver.evidence_prominent_row_keys``) and that carries its
      own disclosed mass, never a blend total lent to it;
    - other callers (the approved probiotic model, omega, multi, readiness,
      confidence) keep the previous rule unchanged: the only scorable active or
      one named in the title (``_is_clear_primary_recovery_row``). Moving them
      to the role owner changes the approved probiotic model's inputs, which
      needs its own measured decision;
    Amount adequacy is owned by Dose. Evidence retains identity, purpose,
    preparation, source-lineage and applicability guards only.
    """
    if matches and not allow_with_existing_matches:
        return []
    from evidence_resolver import evidence_prominent_row_keys, evidence_row_key

    if allow_with_existing_matches:
        if prominent is None:
            prominent = evidence_prominent_row_keys(product)
        if not prominent:
            return []

    existing_ids = {
        _entry_id(entry)
        for entry in matches
        if isinstance(entry, dict)
    }
    existing_refs: Dict[str, set[str]] = defaultdict(set)
    for entry in matches:
        if isinstance(entry, dict):
            existing_refs[_entry_id(entry)].update(
                str(ref).strip()
                for ref in (entry.get("matched_source_row_refs") or [])
                if str(ref or "").strip()
            )
    existing_identity_keys = _existing_match_identity_keys(matches)
    active_canonical_index = _active_canonical_index(product)
    matched_active_canonicals = {
        canonical
        for entry in matches
        if isinstance(entry, dict)
        and (
            canonical := _matched_active_canonical(
                entry,
                active_canonical_index,
                use_structured_identity=allow_with_existing_matches,
            )
        )
    }

    recovered: List[Dict[str, Any]] = []
    for row in nutrient_delivering_rows(product):
        if not isinstance(row, dict):
            continue
        if _is_nutrition_fact_declaration(row):
            continue
        if _norm_text(row.get("evidence_type")) == "blend_anchor_mass":
            # Blend totals are product-level/aggregate evidence. They may recover
            # verified product-level branded studies above, but they must not
            # borrow generic per-ingredient human evidence or primary floors.
            # A disclosed BCAA aggregate is different: the reviewed evidence
            # record itself is for the complete BCAA mixture, and the sports
            # contract already owns that aggregate identity. A protein total is
            # also admitted when enrichment already links evidence.
            from scoring_v4.modules.sports_helpers import BCAA_AGGREGATE_CANONICALS
            blend_canonical = str(row.get("canonical_id") or "").strip().lower()
            if (
                blend_canonical not in BCAA_AGGREGATE_CANONICALS
                and not (allow_with_existing_matches and blend_canonical == "protein")
            ):
                continue
        if allow_with_existing_matches:
            if evidence_row_key(row) not in prominent:
                continue
            if is_lent_blend_mass(row):
                # A blend total lent to one member establishes neither that
                # member's preparation nor its individual exposure.
                continue
        row_canonical_id = str(row.get("canonical_id") or "").strip().lower()
        if row_canonical_id in matched_active_canonicals:
            continue
        row_keys = _row_identity_keys(row)
        if not row_keys:
            continue
        if (
            row_canonical_id == "collagen"
            or _keys_include_dri_essential(row_keys)
            or _keys_include_module_owned_evidence(row_keys)
        ):
            continue
        if not allow_with_existing_matches and not _is_clear_primary_recovery_row(product, row_keys):
            continue

        row_ref = str(row.get("raw_source_path") or row.get("source_row_ref") or "").strip()
        for entry in _verified_ingredient_human_evidence_entries():
            entry_id = _entry_id(entry)
            existing_id = entry_id in existing_ids
            if existing_id and row_canonical_id in matched_active_canonicals:
                continue
            if (
                existing_id and row_ref and row_ref in existing_refs[entry_id]
                and _norm_text(row.get("evidence_type")) != "blend_anchor_mass"
            ):
                # Enrichment already links this record to this very row; a
                # re-stamp would only narrow its source references (to a marker
                # or one oil). The aggregates admitted above (a disclosed BCAA
                # or protein total) are the record's own subject, so binding the
                # record to them stays as before.
                continue
            if _entry_excludes_recovery_context(entry, row, product):
                continue
            entry_keys = _entry_identity_keys(entry)
            matched_keys = row_keys & entry_keys
            if (
                not matched_keys
                and row_canonical_id == "protein"
                and entry_id == "INGR_WHEY_PROTEIN"
            ):
                # Protein grams belong to the macro row; the disclosed source
                # can live in the separate ingredient list. Reuse exact registry
                # identities, never a product title or a generic protein alias.
                # Every declared protein source must qualify: a whey/collagen
                # mixture cannot transfer all its protein grams to whey.
                from scoring_input_contract import declared_protein_source_rows
                source_keys = []
                for source in declared_protein_source_rows(product):
                    forms = [f for f in _safe_list(source.get("forms")) if isinstance(f, dict)]
                    # Lecithin/flavour components do not supply the protein
                    # macro. Unclassified forms still have to prove identity.
                    forms = [f for f in forms if _norm_text(f.get("category")) in {"", "protein"}]
                    if not forms and _row_identity_keys(source) == {"protein"}:
                        continue  # The macro itself cannot establish its source.
                    if _row_identity_keys(source) & entry_keys:
                        # An explicitly identified source remains whey/casein,
                        # even when DSLD also lists its constituent proteins.
                        forms = []
                    for identity in forms or [source]:
                        # Cleaner retains DSLD source identity using camel-case
                        # names/groups; do not discard that existing provenance.
                        keys = _row_identity_keys(identity) | {
                            _canonical_text(identity.get("standardName")),
                            _canonical_text(identity.get("ingredientGroup")),
                        }
                        source_keys.append(keys if source.get("raw_source_path") else set())
                if source_keys and all(keys & entry_keys for keys in source_keys):
                    matched_keys = set().union(*(keys & entry_keys for keys in source_keys))
            if not matched_keys:
                continue
            if not existing_id and existing_identity_keys & entry_keys:
                continue

            recovered_entry = dict(entry)
            recovered_entry["evidence_origin"] = "scoring_contract_recovery"
            recovered_entry["source_data"] = f"backed_clinical_studies:{entry_id}"
            recovered_entry["matched_term"] = row.get("standard_name") or row.get("name")
            recovered_entry["matched_canonical_id"] = row.get("canonical_id")
            _stamp_recovery_source_ref(recovered_entry, row)
            recovered.append(recovered_entry)
            existing_ids.add(entry_id)
            existing_identity_keys.update(entry_keys)
    return recovered


@lru_cache(maxsize=1)
def _verified_product_level_evidence_entries() -> Tuple[Dict[str, Any], ...]:
    try:
        raw = json.loads(_BACKED_CLINICAL_STUDIES_PATH.read_text())
    except Exception:  # pragma: no cover
        return tuple()
    entries = raw.get("backed_clinical_studies") if isinstance(raw, dict) else raw
    out: List[Dict[str, Any]] = []
    for entry in _safe_list(entries):
        if not isinstance(entry, dict):
            continue
        if not _is_verified_product_level_entry(entry):
            continue
        out.append(dict(entry))
    return tuple(out)


@lru_cache(maxsize=1)
def _verified_ingredient_human_evidence_entries() -> Tuple[Dict[str, Any], ...]:
    try:
        raw = json.loads(_BACKED_CLINICAL_STUDIES_PATH.read_text())
    except Exception:  # pragma: no cover
        return tuple()
    entries = raw.get("backed_clinical_studies") if isinstance(raw, dict) else raw
    out: List[Dict[str, Any]] = []
    for entry in _safe_list(entries):
        if not isinstance(entry, dict):
            continue
        if not _is_verified_ingredient_human_entry(entry):
            continue
        out.append(dict(entry))
    return tuple(out)


def _is_verified_product_level_entry(entry: Dict[str, Any]) -> bool:
    if _norm_text(entry.get("study_type")) == "reference":
        return False
    if _norm_text(entry.get("evidence_level")) == "reference":
        return False
    if not _safe_list(entry.get("references_structured")):
        return False
    evidence_level = _norm_text(entry.get("evidence_level"))
    entry_id = _norm_text(entry.get("id"))
    return (
        evidence_level in {"product-human", "product_human", "product-rct", "product_rct", "branded-rct", "branded_rct"}
        or entry_id.startswith("brand_")
    )


def _is_verified_ingredient_human_entry(entry: Dict[str, Any]) -> bool:
    if _norm_text(entry.get("study_type")) == "reference":
        return False
    if _norm_text(entry.get("evidence_level")) == "reference":
        return False
    if not _safe_list(entry.get("references_structured")):
        return False
    return _norm_text(entry.get("evidence_level")) in {
        "ingredient-human",
        "ingredient_human",
    }


def _row_identity_text(
    product: Dict[str, Any], row: Dict[str, Any], *, with_product: bool = True,
) -> str:
    values = [
        product.get("product_name") if with_product else None,
        product.get("name") if with_product else None,
        row.get("name"),
        row.get("standard_name"),
        row.get("raw_source_text"),
        row.get("canonical_id"),
        row.get("scoring_parent_id"),
        row.get("evidence_canonical_id"),
    ]
    return " ".join(_canonical_text(value) for value in values if _canonical_text(value))


def _verified_product_entry_matches_text(entry: Dict[str, Any], row_text: str) -> bool:
    """Exact phrase matching only; no fuzzy clinical-evidence recovery.

    Use branded/product-level identifiers from the verified evidence entry. Broad
    descriptive aliases are deliberately excluded unless the entry itself is not
    branded; this prevents a generic magnolia-phellodendron label from borrowing
    Relora's product-specific RCT unless the label actually says Relora.
    """
    if not row_text:
        return False
    keys: List[str] = []
    entry_id = _norm_text(entry.get("id"))
    if entry_id.startswith("brand_"):
        identifier = entry_id.removeprefix("brand_")
        keys.append(identifier.replace("_", " "))
        keys.append(identifier)
        keys.append(_canonical_text(entry.get("standard_name")))
        # The identifier as labels spell it ("UC-II", "BCM-95", "EGb 761"):
        # only an alias that IS the identifier once separators are removed.
        compact = re.sub(r"[^a-z0-9]", "", identifier)
        keys.extend(
            alias for alias in _safe_list(entry.get("aliases"))
            if re.sub(r"[^a-z0-9]", "", _canonical_text(alias)) == compact
        )
    else:
        keys.extend([_canonical_text(entry.get("standard_name"))])
        keys.extend(_canonical_text(alias) for alias in _safe_list(entry.get("aliases")))

    for key in keys:
        key = _canonical_text(key)
        if not key or len(key) < 4:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", row_text):
            return True
    return False


def _row_identity_keys(row: Dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for value in (
        row.get("canonical_id"),
        row.get("scoring_parent_id"),
        row.get("evidence_canonical_id"),
        row.get("standard_name"),
        row.get("name"),
        row.get("matched_form"),
    ):
        key = _canonical_text(value)
        if key:
            keys.add(key)
    return keys


def _entry_identity_keys(entry: Dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for value in (
        entry.get("canonical_id"),
        entry.get("ingredient_canonical_id"),
        entry.get("standard_name"),
        entry.get("ingredient"),
        entry.get("study_name"),
        entry.get("matched_term"),
    ):
        key = _canonical_text(value)
        if key:
            keys.add(key)
    for alias in _safe_list(entry.get("aliases")):
        key = _canonical_text(alias)
        if key:
            keys.add(key)
    entry_id = str(entry.get("id") or entry.get("study_id") or "")
    if entry_id.upper().startswith("INGR_"):
        key = _canonical_text(entry_id[5:].replace("_", " "))
        if key:
            keys.add(key)
    return keys


def _entry_excludes_recovery_context(
    entry: Dict[str, Any],
    row: Dict[str, Any],
    product: Dict[str, Any],
) -> bool:
    """Honor the enrichment deny-list during scoring-contract recovery.

    Recovery may see both a broad parent identity (for example
    ``standard_name=L-Carnitine``) and a specific raw/form identity (for
    example ``L-Carnitine Fumarate``). An exact excluded form must win over the
    broad parent match, just as it does in the enrichment matcher. Product
    identity is also checked because older enriched rows sometimes retained
    only the broad parent while the product name preserved the specific salt.
    """
    excluded = {
        _canonical_text(value)
        for value in _safe_list(entry.get("exclude_aliases"))
        if _canonical_text(value)
    }
    if not excluded:
        return False
    row_identities = {
        _canonical_text(row.get(field))
        for field in (
            "raw_source_text",
            "name",
            "matched_form",
            "standard_name",
            "canonical_id",
            "scoring_parent_id",
            "evidence_canonical_id",
        )
        if _canonical_text(row.get(field))
    }
    row_identities.update(
        _canonical_text(form.get("name"))
        for form in _safe_list(row.get("forms"))
        if isinstance(form, dict) and _canonical_text(form.get("name"))
    )
    if any(
        _excluded_identity_matches(entry, candidate, excluded)
        for candidate in row_identities
    ):
        return True

    product_identity = _canonical_text(
        " ".join(
            str(product.get(field) or "")
            for field in (
                "product_name",
                "fullName",
                "full_name",
                "name",
            )
        )
    )
    return _excluded_identity_matches(
        entry,
        product_identity,
        excluded,
    )


def _excluded_identity_matches(
    entry: Dict[str, Any],
    candidate: str,
    excluded: set[str],
) -> bool:
    if entry.get("exclude_alias_match_mode") != "bounded_phrase":
        return candidate in excluded
    return any(
        re.search(
            rf"(?<![a-z0-9]){re.escape(excluded_identity)}(?![a-z0-9])",
            candidate,
        )
        for excluded_identity in excluded
    )


def _existing_match_identity_keys(matches: List[Any]) -> set[str]:
    keys: set[str] = set()
    for entry in matches:
        if isinstance(entry, dict):
            keys.update(_entry_identity_keys(entry))
    return keys


@lru_cache(maxsize=1)
def _dri_essential_identity_keys() -> frozenset[str]:
    return frozenset(
        _canonical_text(canonical.replace("_", " "))
        for canonical in DRI_ESSENTIAL_NUTRIENTS
    )


def _keys_include_dri_essential(keys: set[str]) -> bool:
    for key in keys:
        for essential in _dri_essential_identity_keys():
            if not essential:
                continue
            if key == essential or key.startswith(f"{essential} ") or key.endswith(f" {essential}"):
                return True
    return False


@lru_cache(maxsize=1)
def _module_owned_evidence_identity_keys() -> frozenset[str]:
    return frozenset(
        _canonical_text(canonical.replace("_", " "))
        for canonical in _MODULE_OWNED_EVIDENCE_CANONICALS
    )


def _keys_include_module_owned_evidence(keys: set[str]) -> bool:
    for key in keys:
        for owned in _module_owned_evidence_identity_keys():
            if not owned:
                continue
            if key == owned or key.startswith(f"{owned} ") or key.endswith(f" {owned}"):
                return True
    return False


def _is_clear_primary_recovery_row(product: Dict[str, Any], row_keys: set[str]) -> bool:
    """The previous recovery rule, kept unchanged for callers that are not
    owner-scoped: the row is the only scorable active, or the product title
    names it."""
    scorable = [
        ing
        for ing in nutrient_delivering_rows(product)
        if isinstance(ing, dict) and is_scorable(ing)
    ]
    if len(scorable) == 1:
        return True

    title_text = _canonical_text(
        " ".join(
            str(product.get(field) or "")
            for field in ("product_name", "fullName", "full_name", "name")
        )
    )
    if not title_text:
        return False
    for key in row_keys:
        if len(key) < 3:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", title_text):
            return True
    return False


def _collagen_peptide_recovery_row(
    product: Dict[str, Any], *, prominent: Optional[set],
) -> Optional[Dict[str, Any]]:
    """Return the peptide row supplying a recovered study's exposure.

    Owner-scoped recovery requires shared prominence and the exact peptide
    preparation. Amount adequacy belongs to Dose; another collagen preparation
    must never supply this preparation's identity or source binding.
    """
    from evidence_resolver import evidence_row_key

    peptide_row = None
    for row in _competing_active_rows(product):
        if not isinstance(row, dict):
            continue
        if _is_collagen_peptide_row(row) and (
            prominent is None
            or (evidence_row_key(row) in prominent and not is_lent_blend_mass(row))
        ) and (
            peptide_row is None
            or (not _recovery_source_ref(peptide_row) and _recovery_source_ref(row))
        ):
            peptide_row = row
    return peptide_row


def _is_collagen_peptide_row(row: Dict[str, Any]) -> bool:
    if not _has_row_identity(row, "collagen"):
        return False
    subtype = _norm_text(row.get("collagen_subtype"))
    if subtype:
        return subtype == PEPTIDES_I_III
    text = " ".join(
        _norm_text(row.get(key))
        for key in ("matched_form", "name", "standard_name", "raw_source_text")
    )
    return classify_collagen_subtype_strict(text) == PEPTIDES_I_III


def _has_row_identity(row: Dict[str, Any], canonical_id: str) -> bool:
    target = _canonical_text(canonical_id)
    values = (
        row.get("canonical_id"),
        row.get("scoring_parent_id"),
        row.get("evidence_canonical_id"),
        row.get("standard_name"),
        row.get("name"),
        row.get("matched_form"),
    )
    return any(_identity_matches(value, target) for value in values)


def _has_match_for_identity(matches: List[Any], canonical_id: str) -> bool:
    target = _canonical_text(canonical_id)
    for entry in matches:
        if not isinstance(entry, dict):
            continue
        values = (
            entry.get("canonical_id"),
            entry.get("ingredient_canonical_id"),
            entry.get("standard_name"),
            entry.get("ingredient"),
            entry.get("matched_term"),
            entry.get("id"),
        )
        if any(_identity_matches(value, target) for value in values):
            return True
    return False


def _identity_matches(value: Any, target: str) -> bool:
    key = _canonical_text(value)
    if not key:
        return False
    if key == target:
        return True
    # Collagen evidence frequently appears as "hydrolyzed collagen peptides" or
    # INGR_COLLAGEN_PEPTIDES while the active canonical_id is just "collagen".
    return target == "collagen" and "collagen" in key


def _competing_active_rows(
    product: Dict[str, Any],
    rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Actives that compete for mass dominance.

    Must exclude:
    - blend headers (is_proprietary_blend, cleaner_row_role == "blend_header_total")
    - parent totals (is_parent_total, cleaner_row_role == "parent_total")
    - compound duplicates (is_compound_duplicate)
    - undosed children where mass is not known
    A blend total must never compete against an individually dosed active for primary-mass dominance.
    Also removes lineage-owned product_level_evidence totals via primary_mass_competitor_rows.
    """
    if rows is None:
        rows = nutrient_delivering_rows(product)
    raw_competitors = primary_mass_competitor_rows(product, rows)
    competing = []
    for row in raw_competitors:
        if not isinstance(row, dict):
            continue
        if row.get("is_proprietary_blend"):
            continue
        if row.get("is_parent_total"):
            continue
        if row.get("is_compound_duplicate"):
            continue
        if _is_nutrition_fact_declaration(row):
            continue
        role = _norm_text(row.get("cleaner_row_role"))
        if role in {"blend_header_total", "parent_total", "compound_duplicate"}:
            continue
        competing.append(row)
    return competing


def _evidence_anchor_rows(
    product: Dict[str, Any], entry: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """The label identity rows that an evidence match links to.

    A Nutrition Facts declaration or a blend total lent to one child never
    establishes the clinical identity. Linkage
    is the match's single non-structural source row when it names one, else
    every referenced row, else the rows sharing the first identity token
    (canonical, ingredient, standard name, matched term) that names any row.
    """
    rows = [
        row for row in nutrient_delivering_rows(product)
        if isinstance(row, dict)
        and not (_is_nutrition_fact_declaration(row) or is_lent_blend_mass(row))
    ]
    anchor_ref = _unambiguous_non_structural_source_ref(product, entry)
    refs = {anchor_ref} if anchor_ref is not None else {
        str(ref).strip()
        for ref in (entry.get("matched_source_row_refs") or [])
        if str(ref or "").strip()
    }
    if refs:
        return [
            row for row in rows
            if str(row.get("raw_source_path") or row.get("source_row_ref") or "").strip() in refs
        ]
    for tok in (_canonical_from_entry(entry), entry.get("ingredient"),
                entry.get("standard_name"), entry.get("matched_term")):
        key = _norm_text(tok)
        linked = [
            row for row in rows
            if key and key in {
                _norm_text(row.get(field))
                for field in ("canonical_id", "standard_name", "name", "matched_form")
            }
        ]
        if linked:
            return linked
    return []


def _unambiguous_non_structural_source_ref(
    product: Dict[str, Any], entry: Dict[str, Any]
) -> Optional[str]:
    """Return the one identity label row directly referenced by an evidence match.

    ``matched_source_row_refs`` records identity matches and may also contain a
    structural total with the same identity. Only a single referenced,
    non-product-level row establishes the evidence numerator; otherwise the
    historical identity fallback remains in force.
    """
    entry_refs = {
        str(ref).strip()
        for ref in (entry.get("matched_source_row_refs") or [])
        if str(ref or "").strip()
    }
    if not entry_refs:
        return None

    anchors = set()
    for row in nutrient_delivering_rows(product):
        if not isinstance(row, dict):
            continue
        if _norm_text(row.get("scoring_input_kind")) == "product_level_evidence":
            continue
        source_ref = str(
            row.get("raw_source_path") or row.get("source_row_ref") or ""
        ).strip()
        if source_ref in entry_refs:
            anchors.add(source_ref)
    return next(iter(anchors)) if len(anchors) == 1 else None


def _active_canonical_index(product: Dict[str, Any]) -> Dict[str, str]:
    """Map each active's normalized identity tokens -> its raw canonical_id. An
    evidence match resolves to a normalized standard-name (e.g. 'psyllium husk',
    'vitamin d3'); this lets it be tied back to the active's clean canonical_id
    ('psyllium', 'vitamin_d') for the consensus gold-standard allowlist check.
    Evidence subjects without a dose (a blend's disclosed members) are indexed
    too, from the same provider that chose the owners."""
    out: Dict[str, str] = {}
    subjects = [row for row in get_evidence_subject_rows(product) if delivers_its_nutrient(row)]
    for row in nutrient_delivering_rows(product) + subjects:
        if not isinstance(row, dict):
            continue
        cid_raw = str(row.get("canonical_id") or "").strip().lower()
        if not cid_raw:
            continue
        for tok in (row.get("canonical_id"), row.get("standard_name"),
                    row.get("name"), row.get("matched_form")):
            key = _norm_text(tok)
            if key:
                out.setdefault(key, cid_raw)
    return out


def _matched_active_canonical(
    entry: Dict[str, Any],
    canon_index: Dict[str, str],
    *,
    use_structured_identity: bool = False,
    owner_canonicals: Optional[set] = None,
) -> str:
    """Raw canonical_id of the active an evidence match links to ('' if unknown)."""
    reviewed_identity = "matched_canonical_ids" in _safe_dict(entry.get("applicability_assessment"))
    if use_structured_identity or reviewed_identity:
        for canonical_id in _matched_canonical_ids(entry):
            direct = str(canonical_id or "").strip().lower()
            if direct in canon_index.values() and (
                not reviewed_identity or not owner_canonicals or direct in owner_canonicals
            ):
                return direct
        if reviewed_identity:
            # An accepted source identity set (even an empty one) is final.
            # Legacy alias text cannot revive an identity applicability rejected.
            return ""
    for tok in (_canonical_from_entry(entry), entry.get("ingredient"),
                entry.get("standard_name"), entry.get("matched_term")):
        key = _norm_text(tok)
        if key in canon_index:
            return canon_index[key]
    return ""


def _purpose_essential_canonical(
    product: Dict[str, Any], *, owner_canonicals: Optional[set] = None,
) -> Optional[str]:
    """Stable purpose-owned DRI essential for the authority floor.

    The shared role owner supplies ``owner_canonicals``. Amount adequacy and
    excess are independent Dose/Safety judgments and do not decide Evidence.
    """
    candidates = set()
    for row in _competing_active_rows(product):
        if not isinstance(row, dict):
            continue
        canonical = str(row.get("canonical_id") or "").strip().lower()
        if owner_canonicals is not None and canonical not in owner_canonicals:
            continue
        if canonical in DRI_ESSENTIAL_NUTRIENTS and not is_lent_blend_mass(row):
            candidates.add(canonical)
    return sorted(candidates)[0] if candidates else None


def _is_prominent_anchor(
    product: Dict[str, Any], entry: Dict[str, Any], row: Dict[str, Any], prominent: set,
) -> bool:
    """Whether ``row`` is a prominent label row that may carry ``entry``'s amount.

    A row the role owner marks prominent qualifies, including a heading the
    input contract itself resolves to an identity (``identity_bearing``): the
    contract, not this gate, decides that the heading total is that identity's
    amount. Otherwise a blend heading's total
    (``blend_anchor_mass``) is never a member's amount, so it carries only a
    verified product-level record the heading itself names (the registry record
    and predicate product-level recovery use; the heading's own text, never the
    product title), and only when the role owner marks that same label row
    prominent. A member's ingredient record, or a branded member of a larger
    blend, never borrows the total.
    """
    from evidence_resolver import evidence_row_key

    path = str(row.get("raw_source_path") or "").strip()
    record = next(
        (e for e in _verified_product_level_evidence_entries() if _entry_id(e) == _entry_id(entry)),
        None,
    ) if _norm_text(row.get("evidence_type")) == "blend_anchor_mass" else None
    children = [
        child for child in get_assessable_evidence_ingredients(product)
        if path and re.fullmatch(
            re.escape(path) + r"\.nestedRows\[\d+\]", str(child.get("raw_source_path") or "")
        )
    ] if record is not None else []
    if len({child.get("raw_source_path") for child in children}) > 1 and any(
        _verified_product_entry_matches_text(
            record, _row_identity_text(product, child, with_product=False)
        )
        for child in children
    ):
        # Naming a heading after a separately listed branded member does not
        # declare that member's amount. Exact whole-formula headings (Relora,
        # UC-II) remain eligible when their children do not name that record.
        return False
    if evidence_row_key(row) in prominent:
        return True
    if _norm_text(row.get("evidence_type")) != "blend_anchor_mass":
        return False
    if not path or not any(key[0] == path for key in prominent):
        return False
    return record is not None and _verified_product_entry_matches_text(
        record, _row_identity_text(product, row, with_product=False)
    )


def _evidence_matching_mass_mg(row: Dict[str, Any]) -> Optional[float]:
    """Comparable mass used only to link label doses to ingredient evidence."""
    mass = _mass_mg(row)
    if mass is not None:
        return mass

    canonical_id = str(row.get("canonical_id") or "").strip().lower()
    unit = _norm_text(row.get("unit_normalized") or row.get("unit")).replace(" ", "")
    quantity = _as_float(row.get("quantity"), None)
    if (
        canonical_id == "vitamin_d"
        and unit == "iu"
        and quantity is not None
        and quantity > 0
    ):
        return _convert_vitamin_d_evidence_unit(quantity, unit, "mg")
    return None


def _primary_mass_floor(
    product: Dict[str, Any],
    matches: List[Any],
    *,
    prominent: Optional[set] = None,
) -> Tuple[float, Optional[str]]:
    """Evidence floor when a PROMINENT active is strongly & positively evidenced
    at a clinical dose. Returns (floor, canonical) or (0.0, None).

    Which rows may anchor is the shared role owner's decision
    (``evidence_resolver.evidence_prominent_row_keys``), and the match must link
    to such a row (``_is_prominent_anchor``: a blend heading's total only for the
    identity the input contract gives the heading or the branded record its own
    text names; ``_evidence_anchor_rows`` never offers a mass lent to a member
    or a Nutrition Facts declaration). The clinical-dose gates
    stay with the record. When the
    owner names no purpose at all (its retain-everything fallback), there is no
    prominence to read and the previous behavior stands unchanged.

    Amount and studied-dose comparisons are intentionally absent: Dose owns
    adequacy, while this floor owns evidence strength and applicability.
    """
    from evidence_resolver import evidence_prominent_row_keys

    if prominent is None:
        prominent = evidence_prominent_row_keys(product)
    canon_index = _active_canonical_index(product)
    floor = 0.0
    floor_canon: Optional[str] = None
    for entry in matches:
        if not isinstance(entry, dict):
            continue
        effect = _norm_text(entry.get("effect_direction"))
        effect_multiplier = _EFFECT_FLOOR_MULTIPLIER.get(effect, 0.0)
        if effect_multiplier <= 0.0:
            continue
        canonical = _canonical_from_entry(entry)
        if not canonical:
            continue  # can't identify the ingredient -> don't anchor a floor on it
        linked = _evidence_anchor_rows(product, entry)
        if prominent:
            anchors = [row for row in linked if _is_prominent_anchor(product, entry, row, prominent)]
            if not anchors:
                continue  # the evidenced row is not what the label is about
            identities = {str(row.get("canonical_id") or "").strip().lower() for row in anchors}
            linked = [
                row for row in linked
                if str(row.get("canonical_id") or "").strip().lower() in identities
            ]
        st = _norm_text(entry.get("study_type"))
        branded = (
            _norm_text(entry.get("evidence_level")) in _BRANDED_EVIDENCE_LEVELS
            or _norm_text(entry.get("id")).startswith("brand_")
        )
        # 3-lane: brand-specific RCT OR a broad-consensus gold-standard generic
        # both earn the elevated floor; a merely-strong generic literature match
        # does not. Consensus is keyed on the matched ACTIVE's clean canonical_id
        # (not the match's normalized standard-name), so 'psyllium husk' -> psyllium.
        consensus = _matched_active_canonical(entry, canon_index) in _CONSENSUS_GOLD_STANDARD
        elevated = branded or consensus
        if st in _STRONG_STUDY:
            base = PRIMARY_FLOOR_BRANDED_STRONG if elevated else PRIMARY_FLOOR_STRONG
        elif st in _MODERATE_STUDY:
            base = PRIMARY_FLOOR_BRANDED_MODERATE if elevated else PRIMARY_FLOOR_MODERATE
        else:
            base = 0.0
        # Weight the floor by effect strength, mirroring the pipeline's own
        # multiplier so mixed/null evidence gets proportional credit while
        # negative evidence remains ineligible.
        candidate = round(base * effect_multiplier, 4)
        # direction_ceiling (locked 2026-09-18 after the 13-stratum review): a
        # floor may not say more than the evidence direction supports. Only a
        # positive_strong primary may anchor on a STRONG base; every weaker
        # direction is additionally capped at the MODERATE base weighted by the
        # same multiplier already applied above. positive_strong is deliberately
        # excluded, so it keeps the strong/branded base unchanged.
        #
        # No new table: the cap reuses PRIMARY_FLOOR_MODERATE and the multiplier
        # this loop already read from EFFECT_DIRECTION_MULTIPLIERS.
        if effect != "positive_strong":
            candidate = min(candidate, round(PRIMARY_FLOOR_MODERATE * effect_multiplier, 4))
        if candidate > floor:
            floor, floor_canon = candidate, canonical
    return floor, floor_canon


def _entry_raw_points(entry: Dict[str, Any]) -> float:
    base = _as_float(entry.get("base_points"), None)
    if base is None:
        base = STUDY_TYPE_BASE_POINTS.get(_norm_text(entry.get("study_type")), 0.0)

    multiplier = _as_float(entry.get("multiplier"), None)
    if multiplier is None:
        multiplier = EVIDENCE_LEVEL_MULTIPLIERS.get(_norm_text(entry.get("evidence_level")), 0.0)

    raw = base * multiplier
    if raw <= 0:
        return 0.0

    # Missing, unknown, or unresolved direction cannot inherit efficacy. Every
    # shipped evidence record is expected to state this explicitly; malformed
    # or incomplete review data fails closed instead of defaulting positive.
    effect = _norm_text(entry.get("effect_direction"))
    raw *= EFFECT_DIRECTION_MULTIPLIERS.get(effect, 0.0)
    if raw <= 0:
        return 0.0

    study_type = _norm_text(entry.get("study_type"))
    enrollment = _as_float(entry.get("total_enrollment"), None)
    if enrollment is not None and study_type in ENROLLMENT_ELIGIBLE_STUDY_TYPES:
        raw *= _enrollment_multiplier(enrollment)

    return raw


def _entry_id(entry: Dict[str, Any]) -> str:
    explicit = entry.get("id") or entry.get("study_id")
    if explicit:
        return str(explicit)
    return ":".join(
        [
            _canonical_text(entry.get("study_name") or entry.get("ingredient")),
            _norm_text(entry.get("study_type")),
            _norm_text(entry.get("evidence_level")),
        ]
    )


def _canonical_from_entry(entry: Dict[str, Any]) -> str:
    return _canonical_text(
        entry.get("evidence_group_id")
        or entry.get("standard_name")
        or entry.get("study_name")
        or entry.get("ingredient")
    )


def _matched_canonical_ids(entry: Dict[str, Any]) -> List[str]:
    """Return the exact enriched label identities owned by an evidence match."""
    values: List[Any] = []
    assessment = _safe_dict(entry.get("applicability_assessment"))
    if "matched_canonical_ids" in assessment:
        values.extend(_safe_list(assessment.get("matched_canonical_ids")))
    else:
        values.extend(_safe_list(entry.get("matched_canonical_ids")))
        values.extend(_safe_list(entry.get("aggregate_canonical_ids")))
        for key in ("matched_canonical_id", "canonical_id", "ingredient_canonical_id"):
            if entry.get(key):
                values.append(entry.get(key))

    canonical_ids: List[str] = []
    for value in values:
        canonical_id = re.sub(r"[^a-z0-9]+", "_", _norm_text(value)).strip("_")
        if canonical_id and canonical_id not in canonical_ids:
            canonical_ids.append(canonical_id)
    return canonical_ids


def _canonical_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _norm_text(value)).strip()


def _enrollment_multiplier(enrollment: float) -> float:
    for threshold, multiplier in ENROLLMENT_QUALITY_BANDS:
        if enrollment < threshold:
            return multiplier
    return ENROLLMENT_DEFAULT_MULTIPLIER


def _dose_map(product: Dict[str, Any], *, rows=None) -> Dict[str, List[Tuple[float, str]]]:
    """Daily label amounts by source row and by every identity a row names.

    An identity key keeps each amount in its own unit: raw numbers are not
    comparable across units (300 mg vs 10 g, mg vs FU), so the reader converts
    every amount to the evidence record's unit before taking the largest.
    """
    from scoring_input_contract import _positive_quantity, _row_unit
    doses: Dict[str, List[Tuple[float, str]]] = {}
    daily_multiplier = _daily_serving_multiplier(product)
    for ing in nutrient_delivering_rows(product) if rows is None else rows:
        if is_lent_blend_mass(ing):
            # A blend total lent to one child is not that child's amount.
            continue
        quantity = _positive_quantity(ing)
        if quantity is None:
            continue
        quantity *= daily_multiplier
        unit = _norm_text(ing.get("unit_normalized") or _row_unit(ing))
        source_ref = ing.get("raw_source_path") or ing.get("source_row_ref")
        if source_ref:
            doses[f"source:{source_ref}"] = [(quantity, unit)]
        for name in (
            ing.get("standard_name"),
            ing.get("name"),
            ing.get("raw_source_text"),
            ing.get("canonical_id"),
        ):
            key = _canonical_text(name)
            if not key:
                continue
            amounts = doses.setdefault(key, [])
            if (quantity, unit) not in amounts:
                amounts.append((quantity, unit))
    return doses


def _daily_serving_multiplier(product: Dict[str, Any]) -> float:
    """Return the minimum label-directed daily serving count.

    Scoring rows carry the amount per canonical label serving, while clinical
    evidence minima and maxima are daily doses. Delegates to the shared v4
    resolver so this reads the same policy as the dose and safety modules.

    This used to read `serving_basis` alone, which never consulted the label's
    own `servingSizes`, and licensed below-one values on
    `parsed_from_directions` — a flag the enricher sets whenever it parsed the
    directions text at all, not one that says where these values came from.
    """
    return daily_serving_multiplier(product)


def _largest_converted_amount(
    entry: Dict[str, Any],
    amounts: List[Tuple[float, str]],
    dose_unit: str,
) -> Optional[float]:
    # Multiple eligible rows are not summed without an explicit aggregate
    # contract. The largest individually disclosed matching amount wins, judged
    # in the record's unit; an amount that cannot be converted never competes.
    converted = []
    for quantity, unit in amounts:
        value = _convert_unit(quantity, unit, dose_unit)
        if value is None and _is_vitamin_d_evidence_entry(entry):
            value = _convert_vitamin_d_evidence_unit(quantity, unit, dose_unit)
        if value is not None:
            converted.append(value)
    return max(converted, default=None)


def _converted_product_dose(
    entry: Dict[str, Any],
    dose_map: Dict[str, List[Tuple[float, str]]],
) -> tuple[Optional[float], str]:
    # The evidence record's standard name can be less form-specific than the
    # exact label row that enrichment matched.  Resolve the exact match
    # provenance first (e.g. acetyl-L-carnitine hydrochloride), then fall back
    # through structured canonical and study identities.
    refs = entry.get("matched_source_row_refs") or []
    dose_unit = _norm_text(entry.get("dose_unit") or "mg")
    if refs and not entry.get("aggregate_canonical_ids"):
        # Source lineage is authoritative. Never borrow a larger amount from
        # a differently formulated sibling just because canonical IDs agree.
        amounts = [amount for ref in refs for amount in dose_map.get(f"source:{ref}", [])]
        return _largest_converted_amount(entry, amounts, dose_unit), _canonical_from_entry(entry) or ""
    lookup_keys: List[str] = []
    for lookup_name in (
        entry.get("matched_term"),
        entry.get("ingredient"),
        entry.get("matched_canonical_id"),
        entry.get("canonical_id"),
        entry.get("ingredient_canonical_id"),
        entry.get("standard_name"),
        entry.get("study_name"),
    ):
        lookup_key = _canonical_text(lookup_name)
        if lookup_key and lookup_key not in lookup_keys:
            lookup_keys.append(lookup_key)

    product_amounts = None
    resolved_key = lookup_keys[0] if lookup_keys else ""
    for lookup_key in lookup_keys:
        product_amounts = dose_map.get(lookup_key)
        if product_amounts is not None:
            resolved_key = lookup_key
            break
    if product_amounts is not None:
        return _largest_converted_amount(entry, product_amounts, dose_unit), resolved_key

    aggregate_ids = [
        _canonical_text(value)
        for value in _safe_list(entry.get("aggregate_canonical_ids"))
        if _canonical_text(value)
    ]
    if aggregate_ids:
        aggregate_dose = 0.0
        for canonical_id in aggregate_ids:
            converted_component = _largest_converted_amount(
                entry, dose_map.get(canonical_id, []), dose_unit
            )
            if converted_component is None:
                return None, resolved_key
            aggregate_dose += converted_component
        return (
            aggregate_dose,
            _canonical_text(entry.get("evidence_group_id"))
            or _canonical_text(entry.get("standard_name"))
            or resolved_key,
        )

    return None, resolved_key


def _is_vitamin_d_evidence_entry(entry: Dict[str, Any]) -> bool:
    return bool(_entry_identity_keys(entry) & _VITAMIN_D_EVIDENCE_KEYS)


def _convert_vitamin_d_evidence_unit(
    quantity: float,
    from_unit: str,
    to_unit: str,
) -> Optional[float]:
    """Convert Vitamin D IU only for matching an existing evidence row."""
    from_u = _norm_text(from_unit)
    to_u = _norm_text(to_unit)
    if from_u == "iu":
        return _convert_unit(quantity / _VITAMIN_D_IU_PER_MCG, "mcg", to_u)
    if to_u == "iu":
        quantity_mcg = _convert_unit(quantity, from_u, "mcg")
        if quantity_mcg is not None:
            return quantity_mcg * _VITAMIN_D_IU_PER_MCG
    return None


def _convert_unit(quantity: float, from_unit: str, to_unit: str) -> Optional[float]:
    # DSLD spells plural units as Gram(s)/Milligram(s). Normalize only that
    # documented spelling; unrecognized dimensions still return None.
    from_u = _norm_text(from_unit).replace("(s)", "s")
    to_u = _norm_text(to_unit).replace("(s)", "s")
    if from_u == to_u:
        return quantity

    mass_factor = {
        "mcg": 0.001,
        "ug": 0.001,
        "microgram": 0.001,
        "micrograms": 0.001,
        "mg": 1.0,
        "milligram": 1.0,
        "milligrams": 1.0,
        "g": 1000.0,
        "gram": 1000.0,
        "grams": 1000.0,
    }
    if from_u in mass_factor and to_u in mass_factor:
        mg = quantity * mass_factor[from_u]
        return mg / mass_factor[to_u]
    return None


def _published_study_count(entry: Dict[str, Any]) -> Optional[float]:
    explicit = _as_float(entry.get("published_studies_count"), None)
    if explicit is not None:
        return explicit
    # registry_completed_trials_count is discovery/enrichment metadata and,
    # per DATABASE_SCHEMA.md, never a substitute for a published-study count.
    legacy = entry.get("published_studies")
    if isinstance(legacy, (int, float)):
        return _as_float(legacy, None)
    return None


def _depth_bonus(matches: List[Any]) -> float:
    max_count = 0.0
    for entry in matches:
        if not isinstance(entry, dict):
            continue
        count = _published_study_count(entry)
        if count is not None and count > max_count:
            max_count = count

    bonus = 0.0
    for threshold, value in DEPTH_BONUS_BANDS:
        if max_count >= threshold:
            bonus = value
    return bonus


def _append_once(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))
