"""Shared helpers for the v4 sports scoring module."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    get_active_ingredients,
    has_usable_individual_dose,
)


SPORTS_PROTEIN_CANONICALS = frozenset(
    {"protein", "whey_protein", "casein", "pea_protein", "rice_protein", "soy_protein"}
)
CREATINE_CANONICALS = frozenset(
    {
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
)
BETA_ALANINE_CANONICALS = frozenset({"beta-alanine", "beta_alanine"})
CITRULLINE_CANONICALS = frozenset({"l_citrulline"})
HMB_CANONICALS = frozenset({"hmb"})
BCAA_CANONICALS = frozenset({"l_leucine", "l_isoleucine", "l_valine"})
EAA_CANONICALS = frozenset(
    {
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
)
# Non-classic pre-workout / recovery actives with source-verified dose bands
# (see sports_dose._score_primary). BCAA_AGGREGATE is the disclosed
# "branched_chain_amino_acids" total used when the leu/iso/val trio is not split out.
ALPHA_GPC_CANONICALS = frozenset({"alpha_gpc", "alpha_glycerylphosphorylcholine", "choline_alphoscerate"})
ATP_CANONICALS = frozenset({"atp", "adenosine_triphosphate"})
CAFFEINE_CANONICALS = frozenset({"caffeine", "caffeine_anhydrous"})
BETAINE_CANONICALS = frozenset({"betaine", "betaine_anhydrous", "tmg_betaine"})
TAURINE_CANONICALS = frozenset({"taurine"})
BCAA_AGGREGATE_CANONICALS = frozenset({"branched_chain_amino_acids"})
SPORTS_CANONICALS = (
    SPORTS_PROTEIN_CANONICALS
    | CREATINE_CANONICALS
    | BETA_ALANINE_CANONICALS
    | CITRULLINE_CANONICALS
    | HMB_CANONICALS
    | BCAA_CANONICALS
    | EAA_CANONICALS
    | ALPHA_GPC_CANONICALS
    | ATP_CANONICALS
    | CAFFEINE_CANONICALS
    | BETAINE_CANONICALS
    | TAURINE_CANONICALS
    | BCAA_AGGREGATE_CANONICALS
    | frozenset({"agmatine", "l_tyrosine", "l_carnitine"})
)
# Canonicals the sports DOSE rubric has an explicit band for. When a product's
# mass-dominant disclosed active is NOT in this set (e.g. L-carnitine), the sports
# dose dimension falls back to the generic dose-adequacy proxy instead of ignoring
# it, so routing to sports never discards a disclosed primary.
SPORTS_BAND_CANONICALS = (
    SPORTS_PROTEIN_CANONICALS
    | CREATINE_CANONICALS
    | BETA_ALANINE_CANONICALS
    | CITRULLINE_CANONICALS
    | HMB_CANONICALS
    | BCAA_CANONICALS
    | EAA_CANONICALS
    | ALPHA_GPC_CANONICALS
    | ATP_CANONICALS
    | CAFFEINE_CANONICALS
    | BETAINE_CANONICALS
    | TAURINE_CANONICALS
    | BCAA_AGGREGATE_CANONICALS
)
PRE_WORKOUT_CANONICALS = (
    CREATINE_CANONICALS
    | BETA_ALANINE_CANONICALS
    | CITRULLINE_CANONICALS
    | CAFFEINE_CANONICALS
    | BETAINE_CANONICALS
    | TAURINE_CANONICALS
    | ALPHA_GPC_CANONICALS
    | ATP_CANONICALS
    | frozenset({"l_tyrosine", "tyrosine", "acetyl_l_carnitine", "l_carnitine"})
)
STIMULANT_CANONICALS = CAFFEINE_CANONICALS | frozenset(
    {
        "yohimbe",
        "yohimbine",
        "synephrine",
        "green_tea_extract",
        "green_coffee_bean",
        "guarana",
    }
)
ELECTROLYTE_CANONICALS = frozenset({"sodium", "potassium", "magnesium", "calcium", "chloride"})
PRE_WORKOUT_GOAL_CLUSTERS = frozenset(
    {"pre_workout_energy", "pre_post_workout", "muscle_building_recovery"}
)


def canonical(row: Dict[str, Any]) -> str:
    return _norm_text((row or {}).get("canonical_id"))


def dose_g(row: Dict[str, Any]) -> Optional[float]:
    """Return row quantity as grams for mass units, else None."""
    quantity = _as_float((row or {}).get("quantity"), None)
    if quantity is None or quantity <= 0:
        return None

    unit = _norm_text((row or {}).get("unit_normalized") or (row or {}).get("unit"))
    compact = unit.replace(" ", "")
    if unit in {"g", "gram", "grams", "gram(s)"} or compact in {"g", "gram", "grams", "gram(s)"}:
        return quantity
    if unit in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return quantity / 1000.0
    if unit in {"mcg", "ug", "µg", "μg", "microgram", "micrograms", "microgram(s)"}:
        return quantity / 1_000_000.0
    return None


def dose_mg(row: Dict[str, Any]) -> Optional[float]:
    grams = dose_g(row)
    return None if grams is None else grams * 1000.0


def sports_identity_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in get_active_ingredients(product or {}):
        if not isinstance(row, dict):
            continue
        if canonical(row) not in SPORTS_CANONICALS:
            continue
        rows.append(row)
    return rows


def sports_dosed_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in sports_identity_rows(product):
        if not has_usable_individual_dose(row):
            continue
        rows.append(row)
    return rows


def sports_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Backward-compatible alias for dose-bearing sports rows."""
    return sports_dosed_rows(product)


def _row_by_canonical(rows: Iterable[Dict[str, Any]], target: str) -> Optional[Dict[str, Any]]:
    for row in rows:
        if canonical(row) == target:
            return row
    return None


def group_bcaa(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    values: Dict[str, float] = {}
    for key in BCAA_CANONICALS:
        row = _row_by_canonical(rows, key)
        grams = dose_g(row or {})
        if grams is not None:
            values[key] = grams

    complete = BCAA_CANONICALS.issubset(values)
    total = sum(values.values())
    ratio = None
    if complete:
        iso = values["l_isoleucine"]
        val = values["l_valine"]
        divisor = min(iso, val)
        if divisor > 0:
            ratio = (
                round(values["l_leucine"] / divisor, 4),
                round(iso / divisor, 4),
                round(val / divisor, 4),
            )
    return {
        "complete": complete,
        "values_g": values,
        "total_g": total,
        "ratio": ratio,
    }


def group_eaa(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    values: Dict[str, float] = {}
    for row in rows:
        key = canonical(row)
        if key not in EAA_CANONICALS:
            continue
        grams = dose_g(row)
        if grams is not None:
            values[key] = grams
    return {
        "complete": len(values) >= len(EAA_CANONICALS),
        "partial": 6 <= len(values) < len(EAA_CANONICALS),
        "count": len(values),
        "values_g": values,
        "total_g": sum(values.values()),
    }


def primary_sports_identity(product: Dict[str, Any]) -> Optional[str]:
    rows = sports_identity_rows(product)
    canons = {canonical(row) for row in rows}
    name = _norm_text((product or {}).get("product_name") or (product or {}).get("fullName"))

    if canons & SPORTS_PROTEIN_CANONICALS:
        return "protein"
    if CREATINE_CANONICALS & canons:
        return "creatine"
    if group_bcaa(rows)["complete"]:
        return "bcaa"
    if group_eaa(rows)["complete"] and ("eaa" in name or "essential amino" in name):
        return "eaa"
    if BETA_ALANINE_CANONICALS & canons:
        return "beta_alanine"
    if CITRULLINE_CANONICALS & canons:
        return "citrulline"
    if HMB_CANONICALS & canons:
        return "hmb"
    return None


def sports_subtype(product: Dict[str, Any]) -> str:
    """Return the sports subtype used by public calibration and goal routing.

    The module route remains ``sports``. This finer subtype is deliberately
    non-clinical metadata: it prevents a transparent multi-active pre-workout or
    BCAA/EAA formula from inheriting the same public-score ceiling as focused
    creatine/protein products, while preserving the high ceiling for clean
    single-purpose products.
    """
    if not isinstance(product, dict):
        product = {}
    rows = sports_identity_rows(product)
    canons = {canonical(row) for row in rows}
    text = _product_text(product)
    taxonomy = _taxonomy_type(product)

    if _is_opaque_stimulant_context(product, canons, text, taxonomy):
        return "stimulant_fat_burner"
    if _is_protein_context(canons, text, taxonomy):
        return "protein"
    if _is_pre_workout_context(canons, text, taxonomy):
        return "pre_workout"
    if _is_focused_creatine(canons):
        return "creatine"
    if canons & (BCAA_CANONICALS | EAA_CANONICALS | BCAA_AGGREGATE_CANONICALS):
        return "bcaa_eaa"
    if taxonomy == "electrolyte" or any(term in text for term in ("electrolyte", "hydration")):
        return "electrolyte_hydration"
    primary = primary_sports_identity(product)
    if primary in {"creatine", "protein"}:
        return primary
    if primary in {"bcaa", "eaa"}:
        return "bcaa_eaa"
    return primary or "sports_other"


def sports_public_quality_cap(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    subtype = sports_subtype(product)
    if subtype == "stimulant_fat_burner":
        return {
            "id": "sports_opaque_stimulant",
            "cap": 65.0,
            "reason": "Opaque stimulant or fat-burner sports formulas should not rank with transparent sports staples.",
        }
    if subtype == "pre_workout":
        return {
            "id": "sports_pre_workout",
            "cap": 88.0,
            "reason": "Transparent pre-workout stacks are useful but should not score like focused creatine/protein products.",
        }
    if subtype == "bcaa_eaa":
        return {
            "id": "sports_bcaa_eaa",
            "cap": 78.0,
            "reason": "BCAA/EAA products have narrower evidence than complete protein or creatine staples.",
        }
    return None


def pre_workout_goal_cluster_ids(product: Dict[str, Any], *, enforce_dose_gate: bool) -> Set[str]:
    """Direct goal clusters for a true pre-workout.

    Goal matching otherwise sees trace cofactors (zinc, chromium, choline, etc.)
    before it sees the product's real job. For supported goals, require at least
    two disclosed pre-workout anchors at the same evidence-backed floors used by
    the sports dose bands. For the underdosed surface, presence of a real
    pre-workout identity is enough; ``compute_goal_matches`` calls this with
    ``enforce_dose_gate=False`` for its presence-only pass.
    """
    if sports_subtype(product) != "pre_workout":
        return set()
    if not enforce_dose_gate:
        return set(PRE_WORKOUT_GOAL_CLUSTERS)
    return set(PRE_WORKOUT_GOAL_CLUSTERS) if _adequate_pre_workout_anchor_count(product) >= 2 else set()


def _product_text(product: Dict[str, Any]) -> str:
    taxonomy = (product or {}).get("supplement_taxonomy") or {}
    parts = [
        (product or {}).get("product_name"),
        (product or {}).get("fullName"),
        (product or {}).get("brand_name"),
        (product or {}).get("brandName"),
        (product or {}).get("primary_type"),
    ]
    if isinstance(taxonomy, dict):
        parts.extend([taxonomy.get("primary_type"), taxonomy.get("secondary_type"), taxonomy.get("percentile_category")])
    for blend in (product or {}).get("proprietary_blends") or []:
        if isinstance(blend, dict):
            parts.extend([blend.get("name"), blend.get("description")])
    return " ".join(_norm_text(part) for part in parts if _norm_text(part))


def _taxonomy_type(product: Dict[str, Any]) -> str:
    taxonomy = (product or {}).get("supplement_taxonomy") or {}
    direct = _norm_text((product or {}).get("primary_type"))
    if direct:
        return direct
    if isinstance(taxonomy, dict):
        return _norm_text(taxonomy.get("primary_type"))
    return ""


def _is_protein_context(canons: set[str], text: str, taxonomy: str) -> bool:
    if canons & SPORTS_PROTEIN_CANONICALS:
        return True
    if taxonomy == "protein_powder":
        return True
    return "protein" in text and "collagen" not in text


def _is_pre_workout_context(canons: set[str], text: str, taxonomy: str) -> bool:
    preworkout_text = text.replace("-", " ")
    explicit = taxonomy == "pre_workout" or "pre workout" in preworkout_text or "preworkout" in text
    if explicit:
        return bool(canons & PRE_WORKOUT_CANONICALS) or not canons
    if canons & CAFFEINE_CANONICALS and len(canons & (PRE_WORKOUT_CANONICALS - CAFFEINE_CANONICALS)) >= 1:
        return True
    return False


def _is_focused_creatine(canons: set[str]) -> bool:
    non_creatine = canons - CREATINE_CANONICALS
    return bool(canons & CREATINE_CANONICALS) and not non_creatine


def _is_opaque_stimulant_context(
    product: Dict[str, Any],
    canons: set[str],
    text: str,
    taxonomy: str,
) -> bool:
    fat_burner = any(term in text for term in ("fat burner", "fat-burner", "thermogenic", "weight loss", "shred", "cutting"))
    opaque_blend = False
    for blend in (product or {}).get("proprietary_blends") or []:
        if not isinstance(blend, dict):
            continue
        disclosure = _norm_text(blend.get("disclosure_level"))
        if disclosure in {"", "none", "partial"}:
            opaque_blend = True
            break
    stimulant = bool(canons & STIMULANT_CANONICALS)
    preworkout = taxonomy == "pre_workout" or "pre workout" in text.replace("-", " ") or "preworkout" in text
    return (fat_burner and (stimulant or opaque_blend)) or (opaque_blend and (stimulant or preworkout))


def _adequate_pre_workout_anchor_count(product: Dict[str, Any]) -> int:
    rows = sports_dosed_rows(product)
    count = 0
    if _max_g(rows, CREATINE_CANONICALS) is not None and _max_g(rows, CREATINE_CANONICALS) >= 3.0:
        count += 1
    if _max_g(rows, BETA_ALANINE_CANONICALS) is not None and _max_g(rows, BETA_ALANINE_CANONICALS) >= 3.2:
        count += 1
    citrulline = _first_row(rows, CITRULLINE_CANONICALS)
    citrulline_g = dose_g(citrulline or {})
    if citrulline_g is not None:
        label = " ".join(
            _norm_text((citrulline or {}).get(field))
            for field in ("name", "standard_name", "matched_form", "form", "ingredient_form")
        )
        target = 6.0 if "malate" in label else 3.0
        if citrulline_g >= target:
            count += 1
    if _max_mg(rows, CAFFEINE_CANONICALS) is not None and _max_mg(rows, CAFFEINE_CANONICALS) >= 100.0:
        count += 1
    if _max_g(rows, BETAINE_CANONICALS) is not None and _max_g(rows, BETAINE_CANONICALS) >= 2.5:
        count += 1
    return count


def _max_g(rows: Iterable[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[float]:
    values = [dose_g(row) for row in rows if canonical(row) in canonicals]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _max_mg(rows: Iterable[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[float]:
    values = [dose_mg(row) for row in rows if canonical(row) in canonicals]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _first_row(rows: Iterable[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[Dict[str, Any]]:
    for row in rows:
        if canonical(row) in canonicals:
            return row
    return None
