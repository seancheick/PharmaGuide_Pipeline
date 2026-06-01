"""V4 Phase 6 — Botanical Profile (formulation + dose adapters).

Botanicals are not vitamins. The generic A1/A2 (bio_score / premium forms) and
the RDA/UL dose proxy structurally disadvantage herbs. This profile replaces
both for botanical products:

  Formulation adapter (replaces A1/A2, max 15):
    recognized botanical identity        +6
    plant part disclosed                 +2
    quantified dose present              +2
    extract (not whole-herb powder)      +2
    marker standardization declared      +4
    branded clinically-studied extract   +3
    weak / unidentified botanical        -4   (replaces the +6 identity credit)

  Dose adapter (replaces RDA/UL proxy), via rda_therapeutic_dosing.json:
    within studied range   -> 21
    near studied range     -> 16
    below studied range    -> 10
    disclosed, no reference-> 10
    blend total only       -> 7
    primary, no dose       -> 0  (NOT denominator exclusion)

The A5b standardized-botanical bonus is DISABLED inside the profile (marker
standardization is now core formulation, not a duplicate +1 bonus). Botanical
safety cautions are surfaced via confidence; they never override the safety gate.

Spec: docs/superpowers/specs/2026-06-01-v4-botanical-profile-design.md
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

BOTANICAL_FORMULATION_CAP = 15.0

_PLANT_PARTS = (
    "root", "leaf", "leaves", "bark", "flower", "seed", "fruit", "berry",
    "rhizome", "aerial", "bulb", "stem", "rind", "peel", "whole herb", "herb",
    "needle", "resin", "gum", "hull", "shell", "pod",
)
_EXTRACT_TOKENS = ("extract", "extracted", "concentrate", "standardized")
_WHOLE_HERB_TOKENS = ("powder", "whole herb", "whole-herb", "dried herb", "cut")


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _primary_type(product: Dict[str, Any]) -> str:
    ptype = (product or {}).get("primary_type")
    if not (isinstance(ptype, str) and ptype.strip()):
        tax = (product or {}).get("supplement_taxonomy")
        ptype = tax.get("primary_type") if isinstance(tax, dict) else None
    return _norm(ptype)


# --- reference data (loaded + indexed once) --------------------------------

@lru_cache(maxsize=1)
def _dosing_index() -> Dict[str, Dict[str, Any]]:
    """name/alias -> therapeutic dosing entry (typical_dosing_range etc.)."""
    try:
        raw = json.loads((_DATA_DIR / "rda_therapeutic_dosing.json").read_text())
    except Exception:  # pragma: no cover
        return {}
    index: Dict[str, Dict[str, Any]] = {}
    for entry in raw.get("therapeutic_dosing", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                index.setdefault(k, entry)
    return index


@lru_cache(maxsize=1)
def _botanical_identity_set() -> frozenset:
    try:
        raw = json.loads((_DATA_DIR / "botanical_ingredients.json").read_text())
    except Exception:  # pragma: no cover
        return frozenset()
    names = set()
    for entry in raw.get("botanical_ingredients", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("id"), entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                names.add(k)
    return frozenset(names)


@lru_cache(maxsize=1)
def _branded_studied_set() -> frozenset:
    """Normalised names/aliases of branded clinically-studied extracts
    (backed_clinical_studies entries flagged branded / id BRAND_*)."""
    try:
        raw = json.loads((_DATA_DIR / "backed_clinical_studies.json").read_text())
    except Exception:  # pragma: no cover
        return frozenset()
    entries = raw if isinstance(raw, list) else [v for k, v in raw.items() if k != "_metadata"]
    if len(entries) == 1 and isinstance(entries[0], list):
        entries = entries[0]
    names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        is_branded = (
            "branded" in _norm(entry.get("evidence_level"))
            or _norm(entry.get("id")).startswith("brand_")
        )
        if not is_branded:
            continue
        for key in [entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                names.add(k)
    return frozenset(names)


# --- ingredient helpers ----------------------------------------------------

def _scoring_actives(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    iqd = (product or {}).get("ingredient_quality_data") or {}
    rows = iqd.get("ingredients_scorable") or iqd.get("ingredients") or []
    return [r for r in rows if isinstance(r, dict)]


def _is_botanical_active(row: Dict[str, Any]) -> bool:
    tax = row.get("raw_taxonomy") if isinstance(row.get("raw_taxonomy"), dict) else {}
    if _norm(tax.get("category")) == "botanical" or _norm(row.get("category")) == "botanical":
        return True
    names = {_norm(row.get("canonical_id")), _norm(row.get("standard_name")), _norm(row.get("name"))}
    return bool(names & _botanical_identity_set())


def _forms_text(row: Dict[str, Any]) -> str:
    tax = row.get("raw_taxonomy") if isinstance(row.get("raw_taxonomy"), dict) else {}
    pieces = [row.get("matched_form"), row.get("name"), row.get("standard_name")]
    for form in (tax.get("forms") or []) + (row.get("forms") or []):
        if isinstance(form, dict):
            pieces.append(form.get("name"))
        else:
            pieces.append(form)
    return " ".join(_norm(p) for p in pieces if p)


def _ingredient_identity_keys(row: Dict[str, Any]) -> List[str]:
    return [k for k in (_norm(row.get("canonical_id")), _norm(row.get("standard_name")),
                        _norm(row.get("name")), _norm(row.get("matched_form"))) if k]


def _mass_mg(row: Dict[str, Any]) -> Optional[float]:
    qty = _as_float(row.get("quantity"))
    if qty is None or qty <= 0:
        return None
    # Normalize the unit: lowercase, drop spaces and the "(s)" plural marker DSLD
    # uses ("Gram(s)" is the catalog's standard gram spelling — 1906 rows — and
    # must convert to mg, not fall through to the assume-mg branch).
    unit = _norm(row.get("unit") or row.get("unit_normalized")).replace(" ", "")
    unit = unit.replace("(s)", "s")
    if unit in {"mg", "milligram", "milligrams"}:
        return qty
    if unit in {"g", "gram", "grams"}:
        return qty * 1000.0
    if unit in {"mcg", "ug", "µg", "μg", "microgram", "micrograms"}:
        return qty / 1000.0
    return qty  # assume mg when unit absent/unknown (botanicals default to mg)


def _primary_botanical_active(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    botanicals = [r for r in _scoring_actives(product) if _is_botanical_active(r)]
    if not botanicals:
        return None
    # highest comparable mass wins; fall back to first
    return max(botanicals, key=lambda r: (_mass_mg(r) or 0.0))


# --- public API ------------------------------------------------------------

def is_botanical_product(product: Dict[str, Any]) -> bool:
    """A product the botanical profile can actually score: it must have a
    recognizable botanical ACTIVE (taxonomy category 'botanical' or a known
    botanical identity) that is *mass-dominant* over the product's actives.

    Taxonomy primary_type alone is NOT enough — routing a product to the profile
    when the adapters can't find a botanical active would zero its
    formulation/dose (regression). So detection is anchored on the same
    `_primary_botanical_active` the adapters use, keeping router and adapters
    consistent.

    Mass-dominance gate (P6 review): a generic-routed product with a non-botanical
    active that out-masses the botanical (e.g. Magnesium 400 mg + Ginger 50 mg)
    must NOT flip wholesale to the botanical path — that would discard the
    dominant mineral's RDA/UL dose adequacy and A1/A2 form logic and score the
    whole product off a trace herb. The botanical routes only when it is at least
    as massive as the heaviest non-botanical active (comparable mg units; missing
    masses treated as 0, so pure-botanical / anchor-only products still route)."""
    if not isinstance(product, dict):
        return False
    primary = _primary_botanical_active(product)
    if primary is None:
        return False
    botanical_mass = _mass_mg(primary) or 0.0
    non_botanical_masses = [
        _mass_mg(r) or 0.0
        for r in _scoring_actives(product)
        if not _is_botanical_active(r)
    ]
    if max(non_botanical_masses, default=0.0) > botanical_mass:
        return False
    return True


def _standardized_match(product: Dict[str, Any], row: Dict[str, Any]) -> bool:
    sb = ((product.get("formulation_data") or {}).get("standardized_botanicals")) or []
    keys = set(_ingredient_identity_keys(row))
    for item in sb:
        if not isinstance(item, dict) or not item.get("meets_threshold"):
            continue
        item_keys = {_norm(item.get("name")), _norm(item.get("botanical_id")),
                     _norm(item.get("standard_name"))}
        if keys & item_keys:
            return True
    return False


def score_botanical_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Botanical formulation adapter (max 15). Replaces A1/A2 for botanicals."""
    row = _primary_botanical_active(product)
    components: Dict[str, float] = {}
    if row is None:
        return {"score": 0.0, "max": BOTANICAL_FORMULATION_CAP, "components": {},
                "metadata": {"reason": "no_botanical_active"}}

    keys = set(_ingredient_identity_keys(row))
    recognized = bool(keys & _botanical_identity_set()) or (
        bool(_norm(row.get("canonical_id"))) and _norm(
            (row.get("raw_taxonomy") or {}).get("category")) == "botanical"
        and not str(row.get("canonical_id")).startswith("blend")
    )

    if not recognized:
        components["weak_or_unidentified_botanical"] = -4.0
        score = max(0.0, min(BOTANICAL_FORMULATION_CAP, sum(components.values())))
        return {"score": round(score, 4), "max": BOTANICAL_FORMULATION_CAP,
                "components": components, "metadata": {"recognized": False}}

    forms = _forms_text(row)
    components["recognized_botanical_identity"] = 6.0
    if any(re.search(r"\b" + re.escape(pp) + r"\b", forms) for pp in _PLANT_PARTS):
        components["plant_part_disclosed"] = 2.0
    if _mass_mg(row) is not None:
        components["quantified_dose_present"] = 2.0
    if any(tok in forms for tok in _EXTRACT_TOKENS) and "powder" not in forms:
        components["extract_not_whole_herb"] = 2.0
    if _standardized_match(product, row):
        components["marker_standardization_declared"] = 4.0
    if keys & _branded_studied_set():
        components["branded_clinically_studied_extract"] = 3.0

    raw = sum(components.values())
    return {"score": round(min(BOTANICAL_FORMULATION_CAP, max(0.0, raw)), 4),
            "max": BOTANICAL_FORMULATION_CAP,
            "components": components,
            "metadata": {"recognized": True, "raw": round(raw, 4),
                         "cap_applied": raw > BOTANICAL_FORMULATION_CAP}}


def _dosing_entry_for(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    index = _dosing_index()
    for key in _ingredient_identity_keys(row):
        if key in index:
            return index[key]
    return None


def _parse_range(entry: Dict[str, Any]) -> Optional[tuple]:
    rng = _norm(entry.get("typical_dosing_range"))
    m = re.match(r"^\s*([0-9.]+)\s*[-–]\s*([0-9.]+)", rng)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def score_botanical_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Botanical dose adapter via clinical therapeutic ranges. Never returns
    None (a primary botanical with no dose is 0, not denominator-excluded)."""
    row = _primary_botanical_active(product)
    if row is None:
        return {"score": 0.0, "band": "no_botanical_active", "metadata": {}}

    if row.get("is_blend_header") or row.get("blend_total_weight_only") or row.get("is_parent_total"):
        return {"score": 7.0, "band": "blend_total_only", "metadata": {}}

    # P6 review (P2#3): an anchor / product-level-evidence mass is a blend/product
    # TOTAL, not a verified per-ingredient dose. It must not earn within-range
    # credit — otherwise removing the botanical-anchor CAUTION ceiling would
    # over-credit opaque blends. Score it like a blend total.
    if (row.get("scoring_input_kind") == "product_level_evidence"
            or row.get("evidence_type") == "blend_anchor_mass"):
        return {"score": 7.0, "band": "blend_total_only", "metadata": {}}

    mass = _mass_mg(row)
    if mass is None:
        return {"score": 0.0, "band": "primary_no_dose", "metadata": {}}

    entry = _dosing_entry_for(row)
    if entry is None:
        return {"score": 10.0, "band": "disclosed_no_reference", "metadata": {}}

    rng = _parse_range(entry)
    if rng is None:
        return {"score": 10.0, "band": "disclosed_no_reference", "metadata": {}}

    lo, hi = rng
    meta = {"dose_mg": mass, "range": [lo, hi]}
    if lo <= mass <= hi:
        return {"score": 21.0, "band": "within_studied_range", "metadata": meta}
    if 0.8 * lo <= mass < lo or hi < mass <= 1.2 * hi:
        return {"score": 16.0, "band": "near_studied_range", "metadata": meta}
    if mass < 0.8 * lo:
        return {"score": 10.0, "band": "below_studied_range", "metadata": meta}
    # Well above the studied range (P6 review P2#2): a megadose is not evidence-
    # backed and B7 cannot fire for botanicals (no RDA/UL safety flags), so it
    # must NOT earn the same near-range credit as a dose just outside the window.
    # True toxicity is still caught by the Layer-1 safety gate; this is fairness.
    return {"score": 12.0, "band": "above_studied_range", "metadata": meta}
