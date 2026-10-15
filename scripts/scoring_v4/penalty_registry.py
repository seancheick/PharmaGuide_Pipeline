"""Single policy registry for every v4 dimension penalty.

Scoring modules detect facts and calculate magnitudes. This registry owns the
cross-cutting contract: canonical key, primary dimension, and whether an old
location may be migrated centrally. Unknown keys and unapproved dimension drift
fail closed. Additive, sugar and high-risk findings are not dimension penalties:
the formula-checks pillar owns them (V4.1 Step 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class PenaltySpec:
    primary_dimension: str
    consumer_materiality: str
    relocate_legacy_dimension: bool = False


PENALTY_REGISTRY: Dict[str, PenaltySpec] = {
    "immune_high_variability_botanical_stack": PenaltySpec(
        "formulation", "quality_context"
    ),
    "fiber_cleanse_detox_penalty": PenaltySpec(
        "formulation", "quality_context"
    ),
    "fiber_stimulant_laxative_penalty": PenaltySpec(
        "formulation", "consumer_material"
    ),
    "sports_amino_spiking_risk": PenaltySpec(
        "formulation", "quality_context"
    ),
    "sports_collagen_not_complete_protein": PenaltySpec(
        "formulation", "quality_context"
    ),
    "B7_dose_safety": PenaltySpec(
        "dose", "safety_material"
    ),
    "B2_false_allergen_free_claim": PenaltySpec(
        "transparency", "label_integrity"
    ),
    "B5_proprietary_blend_opacity": PenaltySpec(
        "transparency", "label_integrity"
    ),
    "B6_marketing_claims": PenaltySpec("transparency", "label_integrity"),
}


# Omega pre-dates the shared naming convention. Normalize at the orchestration
# boundary so artifacts expose one schema without changing its scoring math.
PENALTY_ALIASES = {
    "b2_false_allergen_free_claim": "B2_false_allergen_free_claim",
    "b5_proprietary_blend_opacity": "B5_proprietary_blend_opacity",
    "b6_marketing_claims": "B6_marketing_claims",
}


#: What each score-bearing component key represents in the public receipt
#: (quality_pillars_v4.<pillar>.receipt). Keys are ``<section>.<key>``; the
#: botanical and collagen profile sections replace ``formulation.A1_bio_score``
#: when a profile applies. Kinds: earned (an assessed property), neutral (a
#: policy baseline or credit for an unknown), disclosure (credit for printing
#: a fact). Penalty keys are always deductions and stay in PENALTY_REGISTRY.
#: An unregistered non-zero component fails closed, as an unregistered penalty
#: does. Rationale: scripts/audits/score_accounting_20261014/AUDIT.md §3.
COMPONENT_KINDS: Dict[str, str] = {
    "formulation.A1_bio_score": "earned",
    "formulation.A3_delivery_system": "earned",
    "formulation.A4_absorption_enhancer": "earned",
    "formulation.A5b_standardized_botanical": "earned",
    "formulation.panel_form_quality": "earned",
    "formulation.b_form_quality": "earned",
    "formulation.form_tier": "earned",
    "formulation.epa_dha_concentration": "earned",
    "formulation.sports_protein_source_quality": "earned",
    "formulation.fiber_source_quality": "earned",
    "botanical_formulation.recognized_botanical_identity": "neutral",
    "botanical_formulation.extract_not_whole_herb": "earned",
    "botanical_formulation.marker_standardization_declared": "earned",
    "botanical_formulation.weak_or_unidentified_botanical": "deduction",
    "collagen_formulation.recognized_collagen_identity": "neutral",
    "collagen_formulation.hydrolyzed_peptides": "earned",
    "dose.supplemental_window_proxy": "earned",
    "dose.botanical_clinical_dose": "earned",
    "dose.collagen_clinical_dose": "earned",
    "dose.joint_support_dose": "earned",
    "dose.sleep_support_dose": "earned",
    "dose.rda_ai_coverage": "earned",
    "dose.critical_nutrient_coverage": "earned",
    "dose.prenatal_complement_support": "earned",
    "dose.b_rda_ai_coverage": "earned",
    "dose.epa_dha_band": "earned",
    "dose.cfu_adequacy": "earned",
    "dose.studied_formula_dose_adequacy": "earned",
    "dose.sports_primary_active_dose": "earned",
    "dose.sports_ratio_or_completeness": "earned",
    "dose.fiber_effective_dose": "earned",
    "dose.vitamin_c_daily_range": "earned",
    "dose.vitamin_d_daily_range": "earned",
    "dose.zinc_daily_range": "earned",
    "dose.copper_balance": "earned",
    "dose.selenium_daily_range": "earned",
    "dose.beta_glucan_disclosed": "earned",
    "dose.quercetin_disclosed": "earned",
    "dose.elderberry_disclosed": "earned",
    "dose.daily_use_discipline": "neutral",
    "evidence.clinical_evidence_pipeline": "earned",
    "evidence.depth_bonus": "earned",
    "evidence.evidence_family_certainty": "earned",
    "evidence.product_applicability": "earned",
    "evidence.independent_replication_consistency": "earned",
    "evidence.clinical_evidence": "earned",
    "evidence.essential_panel_authority": "earned",
    "evidence.b_nutrient_authority_panel": "earned",
    "transparency.clear_disclosure_base": "neutral",
    "transparency.complete_active_identity_dose_disclosure": "disclosure",
    "transparency.B3_claim_compliance": "earned",
    "transparency.hypoallergenic_bonus": "earned",
    "transparency.panel_identity_disclosure": "disclosure",
    "transparency.panel_individual_dose_disclosure": "disclosure",
    "transparency.strain_identities_named": "disclosure",
    "transparency.per_strain_cfu_on_label": "disclosure",
    "transparency.aggregate_cfu_disclosure_proxy": "disclosure",
    "transparency.aggregate_native_afu_disclosure": "disclosure",
    "transparency.epa_or_dha_disclosed": "disclosure",
    "transparency.form_disclosed": "disclosure",
    "transparency.source_disclosed": "disclosure",
}

#: Evidence components that bound the score instead of adding to it:
#: score = min(caps, clamp(max(Σ additive, floor))).
EVIDENCE_FLOOR_KEYS = frozenset({"primary_evidence_floor"})
EVIDENCE_CAP_KEYS = frozenset({"immune_support_evidence_cap", "joint_support_evidence_cap"})


def component_kind(section: str, key: Any) -> str:
    """Receipt kind for one score-bearing component; unknown keys fail closed."""
    kind = COMPONENT_KINDS.get(f"{section}.{key}")
    if kind is None:
        raise RuntimeError(f"unregistered v4 score component: {section}.{key}")
    return kind


def canonical_penalty_key(key: Any) -> str:
    text = str(key)
    return PENALTY_ALIASES.get(text, text)


def penalty_spec(key: Any) -> PenaltySpec:
    canonical = canonical_penalty_key(key)
    spec = PENALTY_REGISTRY.get(canonical)
    if spec is None:
        raise RuntimeError(f"unregistered v4 penalty key: {key!r}")
    return spec


def _normalise_penalty_keys(penalties: Dict[str, Any]) -> None:
    for old_key in list(penalties):
        canonical = canonical_penalty_key(old_key)
        if canonical == old_key:
            continue
        if canonical in penalties:
            raise RuntimeError(
                f"both legacy and canonical penalty keys emitted: {old_key!r}, "
                f"{canonical!r}"
            )
        penalties[canonical] = penalties.pop(old_key)


def apply_penalty_registry(module_result: Any) -> bool:
    """Normalize, relocate approved legacy debt, and validate every penalty.

    Returns True when score-bearing locations changed and the caller must
    reassemble the module total.
    """
    dimensions = getattr(module_result, "dimensions", None)
    if not isinstance(dimensions, dict):
        raise RuntimeError("v4 module result has no dimensions for penalty policy")

    for dimension in dimensions.values():
        penalties = getattr(dimension, "penalties", None)
        if not isinstance(penalties, dict):
            raise RuntimeError("v4 dimension has no penalty mapping")
        _normalise_penalty_keys(penalties)

    changed = False
    relocations = []
    for source_name, source in dimensions.items():
        for key in list(source.penalties):
            spec = penalty_spec(key)
            if spec.primary_dimension == source_name:
                continue
            if not spec.relocate_legacy_dimension:
                raise RuntimeError(
                    f"penalty {key!r} emitted in {source_name!r}; "
                    f"registered primary dimension is {spec.primary_dimension!r}"
                )
            target = dimensions.get(spec.primary_dimension)
            if target is None:
                raise RuntimeError(
                    f"penalty {key!r} targets missing dimension "
                    f"{spec.primary_dimension!r}"
                )
            if key in target.penalties:
                raise RuntimeError(f"penalty {key!r} emitted in two dimensions")

            value = float(source.penalties.pop(key) or 0.0)
            magnitude = abs(value)
            target.penalties[key] = -magnitude
            source.score = round(
                min(float(source.max), float(source.score or 0.0) + magnitude),
                4,
            )
            target.score = round(max(0.0, float(target.score or 0.0) - magnitude), 4)
            relocations.append(
                {
                    "penalty": key,
                    "from": source_name,
                    "to": spec.primary_dimension,
                    "magnitude": magnitude,
                }
            )
            changed = True

    # Validate again after migration; this also catches an unknown key in a
    # route that happened not to need relocation.
    for dimension_name, dimension in dimensions.items():
        for key in dimension.penalties:
            spec = penalty_spec(key)
            if spec.primary_dimension != dimension_name:
                raise RuntimeError(
                    f"penalty {key!r} remains outside its registered dimension"
                )

    if relocations:
        metadata = getattr(module_result, "metadata", None)
        if not isinstance(metadata, dict):
            raise RuntimeError("v4 module result has no metadata for penalty policy")
        metadata["penalty_relocations"] = relocations
    return changed
