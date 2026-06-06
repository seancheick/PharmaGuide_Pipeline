"""v4 generic-module Evidence dimension (P1.3.3).

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 generic rubric, Evidence 20
preserves the Section C multiplicative pipeline:

    study_type × evidence_level × effect_direction × enrollment × dose_guard
    → cap per ingredient → top-N diminishing returns → depth bonus → cap 20

This is a v4-owned implementation. It intentionally does not import the
v3 scorer, but it reads the same enriched `evidence_data.clinical_matches`
contract so shadow comparisons stay explainable.
"""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Dict, List, Optional, Tuple

from collagen_taxonomy import PEPTIDES_I_III, classify_collagen_subtype_strict
from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    get_active_ingredients,
)
from scoring_v4.modules.botanical_profile import _mass_mg
from scoring_v4.modules.collagen_profile import is_collagen_product


PHASE_MARKER = "P1.3.3_evidence_pipeline"

CAP_TOTAL = 20.0
CAP_PER_INGREDIENT = 7.0
SUPRA_CLINICAL_MULTIPLE = 3.0
SUB_CLINICAL_DOSE_GUARD_MULTIPLIER = 0.25

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

EFFECT_DIRECTION_MULTIPLIERS: Dict[str, float] = {
    "positive_strong": 1.0,
    "positive_weak": 0.85,
    "mixed": 0.6,
    "null": 0.25,
    "negative": 0.0,
}

ENROLLMENT_ELIGIBLE_STUDY_TYPES = frozenset(
    {"systematic_review_meta", "rct_multiple", "rct_single"}
)
ENROLLMENT_QUALITY_BANDS = (
    (50.0, 0.6),
    (200.0, 0.8),
    (500.0, 1.0),
    (1000.0, 1.1),
)
ENROLLMENT_DEFAULT_MULTIPLIER = 1.2

TOP_N_WEIGHTS = (1.0, 0.7, 0.5, 0.3)
DEPTH_BONUS_BANDS = ((20.0, 0.25), (40.0, 0.5))

# Phase 8 — primary-ingredient evidence floor (PROTOTYPE). The top-N additive
# pipeline rewards ingredient COUNT: a focused single clinically-validated
# ingredient (KSM-66) scores ~4.5/20 while two generic minerals score ~11.5/20.
# When the product's MASS-DOMINANT active is a strongly-evidenced, positively-
# effective, clinically-dosed ingredient, the dimension earns a floor so quality
# is rewarded independent of count. Keyed on the mass-dominant active (the evidence
# match must link to an active whose mass >= PRIMARY_MASS_FRACTION of the heaviest
# active), NOT merely the top evidence-points contributor — otherwise a well-studied
# TRACE co-ingredient (calcium in a protein powder) would wrongly float the product.
PRIMARY_FLOOR_STRONG = 18.0     # systematic review / multi-RCT, positive, clinical dose
PRIMARY_FLOOR_MODERATE = 11.0   # single RCT / clinical strain, positive, clinical dose
# v4.1 branded-RCT tier: a branded clinically-studied extract (Sensoril, KSM-66,
# Meriva/BCM-95 — its OWN brand-specific RCT evidence, not a generic literature
# match) earns a higher floor than a non-branded ingredient at the same study tier.
# 18 (branded + meta/multi-RCT) / 17 (branded + single RCT). 19-20 stays reserved
# for multi-active breadth, so a single extract can be "excellent" but not "perfect".
PRIMARY_FLOOR_BRANDED_STRONG = 18.0
PRIMARY_FLOOR_BRANDED_MODERATE = 17.0
_BRANDED_EVIDENCE_LEVELS = frozenset({"branded-rct", "branded_rct"})
_STRONG_STUDY = frozenset({"systematic_review_meta", "rct_multiple"})
_MODERATE_STUDY = frozenset({"rct_single", "clinical_strain"})
# Effect-strength weight on the primary floor. Mirrors the pipeline's effect
# multipliers so honest mixed/null human evidence receives proportional credit
# instead of falling through to raw low-count pipeline math. Negative evidence
# remains zero and never anchors a floor.
_EFFECT_FLOOR_MULTIPLIER = {
    "positive_strong": 1.0,
    "positive_weak": 0.85,
    "mixed": 0.6,
    "null": 0.25,
}
# Prototype toggle (Phase 8 spike). Set ENABLED=False for the no-floor baseline.
# The floor is gated on the strongly-evidenced ingredient being a MASS-DOMINANT
# active (mass >= PRIMARY_MASS_FRACTION of the heaviest active), so it rewards a
# product whose PRIMARY ingredient is well-studied (KSM-66, Niacin) and never
# floats a product on a well-studied TRACE co-ingredient (calcium in a protein
# powder) — the failure the focus-gate benchmark surfaced.
PRIMARY_FLOOR_ENABLED = True
PRIMARY_MASS_FRACTION = 0.5

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


def score_evidence(product: Dict[str, Any], *, apply_primary_floor: bool = False) -> Dict[str, Any]:
    """Compute the generic-module Evidence dimension.

    Returns a dimension payload compatible with
    `GenericModuleResult.dimensions["evidence"]`.

    `apply_primary_floor`: the Phase-8 primary-ingredient floor is opt-in per
    caller. Only the GENERIC module (which has the count-over-quality flaw) passes
    True. omega / probiotic / multi / sports reuse this scorer as a sub-component
    and have their own evidence logic, so they must NOT inherit the floor.
    """
    if not isinstance(product, dict):
        product = {}

    matches = list(_safe_list(_safe_dict(product.get("evidence_data")).get("clinical_matches")))
    recovered_matches = _recover_contract_evidence_matches(product, matches)
    if recovered_matches:
        matches.extend(recovered_matches)
    dose_map = _dose_map(product)
    ingredient_points: Dict[str, float] = defaultdict(float)
    matched_entry_ids: set[str] = set()
    flags: List[str] = []
    sub_clinical_canonicals: set[str] = set()

    for entry in matches:
        if not isinstance(entry, dict):
            continue
        entry_id = _entry_id(entry)
        if entry_id in matched_entry_ids:
            continue
        matched_entry_ids.add(entry_id)

        raw = _entry_raw_points(entry)
        if raw <= 0:
            continue

        converted_dose, lookup_key = _converted_product_dose(entry, dose_map)
        min_clinical_dose = _as_float(entry.get("min_clinical_dose"), None)
        if (
            min_clinical_dose is not None
            and converted_dose is not None
            and converted_dose < min_clinical_dose
        ):
            raw *= SUB_CLINICAL_DOSE_GUARD_MULTIPLIER
            _append_once(flags, "SUB_CLINICAL_DOSE_DETECTED")
            canonical = _canonical_from_entry(entry) or lookup_key
            if canonical:
                sub_clinical_canonicals.add(canonical)

        max_studied_dose = _as_float(
            entry.get("max_studied_clinical_dose")
            or entry.get("max_clinical_dose")
            or entry.get("max_studied_dose"),
            None,
        )
        if (
            converted_dose is not None
            and max_studied_dose is not None
            and max_studied_dose > 0
            and converted_dose > (SUPRA_CLINICAL_MULTIPLE * max_studied_dose)
        ):
            _append_once(flags, "SUPRA_CLINICAL_DOSE")

        marker_confidence = entry.get("marker_confidence_scale")
        if marker_confidence is not None:
            scale = _as_float(marker_confidence, None)
            if scale is not None:
                raw *= scale

        canonical = _canonical_from_entry(entry)
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

    depth_bonus = _depth_bonus(matches)

    # Phase 8 — primary-ingredient evidence floor. The TOP evidence contributor
    # (highest points, excluding sub-clinical) anchors a floor when it is strongly
    # & positively evidenced, so a focused premium ingredient isn't out-scored by
    # ingredient count.
    primary_floor = 0.0
    floor_canonical: Optional[str] = None
    if apply_primary_floor and PRIMARY_FLOOR_ENABLED:
        primary_floor, floor_canonical = _primary_mass_floor(
            product, matches, sub_clinical_canonicals
        )

    total = _clamp(0.0, CAP_TOTAL, max(pipeline_total + depth_bonus, primary_floor))

    components = {
        "clinical_evidence_pipeline": round(pipeline_total, 4),
        "depth_bonus": round(depth_bonus, 4),
    }
    if primary_floor > 0.0:
        components["primary_evidence_floor"] = round(primary_floor, 4)

    return {
        "score": round(total, 4),
        "max": CAP_TOTAL,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "ingredient_points": {k: round(v, 4) for k, v in sorted(ingredient_points.items())},
            "matched_entries": len(matched_entry_ids),
            "top_n_applied": min(len(capped_scores), len(TOP_N_WEIGHTS)),
            "sub_clinical_canonicals": sorted(sub_clinical_canonicals),
            "primary_evidence_floor": round(primary_floor, 4),
            "primary_evidence_floor_canonical": floor_canonical,
            "recovered_matches": [
                _entry_id(entry)
                for entry in recovered_matches
            ],
            "flags": flags,
        },
    }


def _recover_contract_evidence_matches(
    product: Dict[str, Any],
    matches: List[Any],
) -> List[Dict[str, Any]]:
    """Recover evidence when the scoring input contract has a clear primary
    identity but enrichment failed to copy the corresponding clinical match.

    Keep this deliberately narrow. It currently only handles collagen because
    the project has verified collagen-peptide evidence in
    backed_clinical_studies.json and the collagen profile already proves product
    ownership via mass/intent. Token collagen add-ons stay excluded by
    is_collagen_product().
    """
    if not _has_primary_collagen_peptide_identity(product):
        return []
    if _has_match_for_identity(matches, "collagen"):
        return []
    if not is_collagen_product(product):
        return []
    return [dict(_RECOVERED_COLLAGEN_PEPTIDES_MATCH)]


def _has_primary_collagen_peptide_identity(product: Dict[str, Any]) -> bool:
    max_active_mass = 0.0
    max_peptide_mass = 0.0
    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        mass = _mass_mg(row) or 0.0
        max_active_mass = max(max_active_mass, mass)
        if _is_collagen_peptide_row(row):
            max_peptide_mass = max(max_peptide_mass, mass)
    if max_peptide_mass <= 0.0:
        return False
    if max_active_mass <= 0.0:
        return False
    return max_peptide_mass >= (PRIMARY_MASS_FRACTION * max_active_mass)


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


def _active_mass_index(product: Dict[str, Any]) -> Tuple[Dict[str, float], float]:
    """Map each active's normalized identity tokens -> its mass (mg), plus the
    heaviest active mass. Used to link an evidence match back to the active it
    came from and decide whether that active is mass-dominant."""
    index: Dict[str, float] = {}
    max_mass = 0.0
    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        mass = _mass_mg(row) or 0.0
        if mass <= 0:
            continue
        max_mass = max(max_mass, mass)
        for tok in (row.get("canonical_id"), row.get("standard_name"),
                    row.get("name"), row.get("matched_form")):
            key = _norm_text(tok)
            if key:
                index[key] = max(index.get(key, 0.0), mass)
    return index, max_mass


def _match_active_mass(entry: Dict[str, Any], index: Dict[str, float]) -> float:
    """Mass of the active an evidence match links to (0 if not found). Links by
    normalized identity (match ingredient/standard_name/matched_term/canonical)."""
    for tok in (_canonical_from_entry(entry), entry.get("ingredient"),
                entry.get("standard_name"), entry.get("matched_term")):
        key = _norm_text(tok)
        if key and key in index:
            return index[key]
    return 0.0


def _primary_mass_floor(
    product: Dict[str, Any],
    matches: List[Any],
    sub_clinical_canonicals: set,
) -> Tuple[float, Optional[str]]:
    """Evidence floor when the MASS-DOMINANT active is strongly & positively
    evidenced at a clinical dose. Returns (floor, canonical) or (0.0, None)."""
    index, max_mass = _active_mass_index(product)
    if max_mass <= 0:
        return 0.0, None
    threshold = PRIMARY_MASS_FRACTION * max_mass
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
        if canonical in sub_clinical_canonicals:
            continue
        if _match_active_mass(entry, index) < threshold:
            continue  # the evidenced ingredient is not a mass-dominant active
        st = _norm_text(entry.get("study_type"))
        branded = _norm_text(entry.get("evidence_level")) in _BRANDED_EVIDENCE_LEVELS
        if st in _STRONG_STUDY:
            base = PRIMARY_FLOOR_BRANDED_STRONG if branded else PRIMARY_FLOOR_STRONG
        elif st in _MODERATE_STUDY:
            base = PRIMARY_FLOOR_BRANDED_MODERATE if branded else PRIMARY_FLOOR_MODERATE
        else:
            base = 0.0
        # Weight the floor by effect strength, mirroring the pipeline's own
        # multiplier so mixed/null evidence gets proportional credit while
        # negative evidence remains ineligible.
        candidate = round(base * effect_multiplier, 4)
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

    effect = _norm_text(entry.get("effect_direction") or "positive_strong")
    raw *= EFFECT_DIRECTION_MULTIPLIERS.get(effect, 1.0)
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
    return _canonical_text(entry.get("standard_name") or entry.get("study_name") or entry.get("ingredient"))


def _canonical_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _norm_text(value)).strip()


def _enrollment_multiplier(enrollment: float) -> float:
    for threshold, multiplier in ENROLLMENT_QUALITY_BANDS:
        if enrollment < threshold:
            return multiplier
    return ENROLLMENT_DEFAULT_MULTIPLIER


def _dose_map(product: Dict[str, Any]) -> Dict[str, Tuple[float, str]]:
    doses: Dict[str, Tuple[float, str]] = {}
    for ing in get_active_ingredients(product):
        quantity = _as_float(ing.get("quantity"), None)
        if quantity is None:
            continue
        unit = _norm_text(ing.get("unit_normalized") or ing.get("unit"))
        for name in (
            ing.get("standard_name"),
            ing.get("name"),
            ing.get("raw_source_text"),
            ing.get("canonical_id"),
        ):
            key = _canonical_text(name)
            if not key:
                continue
            if key not in doses or quantity > doses[key][0]:
                doses[key] = (quantity, unit)
    return doses


def _converted_product_dose(
    entry: Dict[str, Any],
    dose_map: Dict[str, Tuple[float, str]],
) -> tuple[Optional[float], str]:
    lookup_name = entry.get("standard_name") or entry.get("study_name") or entry.get("ingredient") or ""
    lookup_key = _canonical_text(lookup_name)
    product_dose = dose_map.get(lookup_key)
    if product_dose is None:
        return None, lookup_key
    dose_unit = _norm_text(entry.get("dose_unit") or "mg")
    return _convert_unit(product_dose[0], product_dose[1], dose_unit), lookup_key


def _convert_unit(quantity: float, from_unit: str, to_unit: str) -> Optional[float]:
    from_u = _norm_text(from_unit)
    to_u = _norm_text(to_unit)
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
    registry = _as_float(entry.get("registry_completed_trials_count"), None)
    if registry is not None:
        return registry
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
