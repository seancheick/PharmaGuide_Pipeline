"""Shared helpers for the v4 sports scoring module."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

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
