"""Single policy registry for every v4 dimension penalty.

Scoring modules detect facts and calculate magnitudes. This registry owns the
cross-cutting contract: canonical key, primary dimension, optional consumer
mirror group, and whether an old location may be migrated centrally. Unknown
keys and unapproved dimension drift fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class PenaltySpec:
    primary_dimension: str
    consumer_materiality: str
    mirror_group: Optional[str] = None
    relocate_legacy_dimension: bool = False


FORMULA_QUALITY_MIRROR = "formula_quality_checks"
DOSE_LIMIT_MIRROR = "dose_limit"


PENALTY_REGISTRY: Dict[str, PenaltySpec] = {
    "B0_moderate_watchlist": PenaltySpec("formulation", "safety_context"),
    "B1_dietary_sugar": PenaltySpec(
        "formulation", "consumer_material", FORMULA_QUALITY_MIRROR
    ),
    "B1_harmful_additives": PenaltySpec(
        "formulation", "consumer_material", FORMULA_QUALITY_MIRROR
    ),
    "B1_sleep_melatonin_gummy": PenaltySpec(
        "formulation", "consumer_material", FORMULA_QUALITY_MIRROR
    ),
    "B1_immune_gummy_or_syrup": PenaltySpec(
        "formulation", "consumer_material"
    ),
    "gummy_formulation_limit": PenaltySpec(
        "formulation", "consumer_material"
    ),
    "immune_high_variability_botanical_stack": PenaltySpec(
        "formulation", "quality_context"
    ),
    "fiber_gummy_delivery_penalty": PenaltySpec(
        "formulation", "consumer_material"
    ),
    "fiber_cleanse_detox_penalty": PenaltySpec(
        "formulation", "quality_context"
    ),
    "fiber_stimulant_laxative_penalty": PenaltySpec(
        "formulation", "consumer_material"
    ),
    "sports_artificial_sweeteners": PenaltySpec(
        "formulation", "consumer_material"
    ),
    "sports_opaque_protein_blend": PenaltySpec(
        "formulation", "quality_context"
    ),
    "sports_amino_spiking_risk": PenaltySpec(
        "formulation", "quality_context"
    ),
    "sports_collagen_not_complete_protein": PenaltySpec(
        "formulation", "quality_context"
    ),
    "B7_dose_safety": PenaltySpec(
        "dose", "safety_material", DOSE_LIMIT_MIRROR
    ),
    # The immune profile historically emitted this from Formulation despite
    # detecting a dose fact. The central adapter migrates it once, then validates.
    "B7_immune_high_zinc_daily_use": PenaltySpec(
        "dose",
        "safety_material",
        DOSE_LIMIT_MIRROR,
        relocate_legacy_dimension=True,
    ),
    "opaque_primary_sports_blend": PenaltySpec("dose", "quality_context"),
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


def mirrored_penalty_magnitude(
    module_breakdown: Mapping[str, Any],
    mirror_group: str,
) -> float:
    """Return registered negative penalty magnitude for one consumer mirror."""
    dimensions = module_breakdown.get("dimensions")
    if not isinstance(dimensions, Mapping):
        return 0.0
    total = 0.0
    for dimension_name, raw_dimension in dimensions.items():
        if not isinstance(raw_dimension, Mapping):
            continue
        penalties = raw_dimension.get("penalties")
        if not isinstance(penalties, Mapping):
            continue
        for raw_key, raw_value in penalties.items():
            spec = penalty_spec(raw_key)
            if spec.primary_dimension != dimension_name:
                raise RuntimeError(
                    f"artifact penalty {raw_key!r} is in {dimension_name!r}, "
                    f"expected {spec.primary_dimension!r}"
                )
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"penalty {raw_key!r} has non-numeric value"
                ) from exc
            if spec.mirror_group == mirror_group and value < 0:
                total += abs(value)
    return round(total, 4)
