"""V4 Phase 7 — Collagen Profile (formulation + dose adapters).

Collagen is neither a vitamin nor a botanical. The plan's original premise
(collagen evidence averages 1.1/20) was stale — by Phase 6 the generic evidence
pipeline already gives collagen ~6.3/20. The real gap is DOSE: a collagen product
borrows its co-formulated vitamins' RDA/UL dose, so an underdosed collagen (2.5 g
vs the studied 2.5-10 g for peptides) over-scores. This profile scores collagen on its own
clinical dose range and formulation quality, mass-dominance routed (a multivitamin
with a token collagen add-on stays on the generic path).

  Formulation adapter (replaces A1/A2, max 15):
    recognized collagen identity         +6
    hydrolyzed peptides (not gelatin)    +2
    collagen type disclosed (I/II/III…)  +3
    source disclosed (marine/bovine/…)   +2
    quantified dose present              +2
    branded clinically-studied collagen  +3

  Dose adapter (replaces RDA/UL proxy), via rda_therapeutic_dosing.json
  per collagen subtype (peptides 2.5-10 g, UC-II 40 mg, BioCell 500-2000 mg,
  gelatin 5-15 g, NEM 500 mg) — UNIT-AWARE (gram entries vs mg, masses are
  normalized to mg):
    within studied range   -> 21
    near studied range     -> 16
    below studied range    -> 10   (the underdosed-collagen honesty case)
    above studied range    -> 12
    disclosed, no reference-> 10
    blend / anchor total   -> 7
    primary, no dose       -> 0    (NOT denominator exclusion)

Reuses the shared identity/mass/dosing helpers from botanical_profile so unit
normalization (incl. DSLD "Gram(s)") and routing stay consistent across profiles.

Spec: docs/superpowers/specs/2026-06-01-v4-collagen-profile-design.md
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from collagen_taxonomy import classify_collagen_subtype, SUBTYPE_TO_DOSING_ALIAS
from scoring_v4.modules.botanical_profile import (
    _norm,
    _mass_mg,
    _scoring_actives,
    _forms_text,
    _ingredient_identity_keys,
    _dosing_index,
)

COLLAGEN_FORMULATION_CAP = 15.0

_COLLAGEN_TOKENS = ("collagen", "gelatin")
_HYDROLYZED_TOKENS = ("hydrolyzed", "hydrolysed", "hydrolysate", "peptide")
_SOURCE_TOKENS = ("marine", "bovine", "chicken", "porcine", "fish", "grass-fed",
                  "grass fed", "eggshell", "sternal cartilage")
_TYPE_RE = re.compile(r"\btype\s*(i{1,3}|1|2|3|iv|v|x)\b|\buc-?ii\b|undenatured")
# Real branded clinically-studied collagen ingredients. This is a label-fidelity
# (formulation-quality) signal — "the product uses a recognized branded extract" —
# NOT an evidence/citation claim.
_COLLAGEN_BRANDS = ("verisol", "biocell", "fortigel", "fortibone", "peptan",
                    "naticol", "bodybalance", "tendoforte", "ucii", "uc-ii")


def _identity_text(row: Dict[str, Any]) -> str:
    return _forms_text(row) + " " + " ".join(_ingredient_identity_keys(row))


def _is_collagen_active(row: Dict[str, Any]) -> bool:
    if _norm(row.get("canonical_id")) == "collagen":
        return True
    return any(t in _identity_text(row) for t in _COLLAGEN_TOKENS)


def _primary_collagen_active(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rows = [r for r in _scoring_actives(product) if _is_collagen_active(r)]
    if not rows:
        return None
    return max(rows, key=lambda r: (_mass_mg(r) or 0.0))


# --- public API ------------------------------------------------------------

def is_collagen_product(product: Dict[str, Any]) -> bool:
    """A product the collagen profile can score: a recognizable collagen active
    that is mass-dominant over the product's actives (so a multivitamin with a
    token collagen add-on keeps the generic vitamin/mineral path). Mirrors the
    Phase-6 botanical mass-dominance gate."""
    if not isinstance(product, dict):
        return False
    primary = _primary_collagen_active(product)
    if primary is None:
        return False
    collagen_mass = _mass_mg(primary) or 0.0
    non_collagen = [
        _mass_mg(r) or 0.0
        for r in _scoring_actives(product)
        if not _is_collagen_active(r)
    ]
    if max(non_collagen, default=0.0) > collagen_mass:
        return False
    return True


def _collagen_dosing_entry(row: Dict[str, Any],
                           product: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Match a collagen row to the correct clinical-dose entry by subtype. Each
    collagen type has a distinct studied dose (UC-II 40 mg, NEM 500 mg, BioCell /
    hydrolyzed Type II 500-2000 mg, hydrolyzed peptides 2.5-10 g, gelatin 5-15 g),
    so a single generic entry would mis-score the low-mg subtypes.

    Prefers the authoritative `collagen_subtype` the enricher stamps on the row;
    falls back to the shared `classify_collagen_subtype` text classifier when the
    field is absent (older enriched corpus) or unrecognized. Both paths use the
    same taxonomy (collagen_taxonomy.py) — single source of truth."""
    index = _dosing_index()
    subtype = _norm(row.get("collagen_subtype"))
    if subtype not in SUBTYPE_TO_DOSING_ALIAS:
        product_name = product.get("product_name") if isinstance(product, dict) else None
        subtype = classify_collagen_subtype(_identity_text(row), product_name)
    return index.get(SUBTYPE_TO_DOSING_ALIAS[subtype])


def _parse_dose_range(entry: Dict[str, Any]) -> Optional[tuple]:
    """Parse 'lo-hi' or a single 'value' (point dose, e.g. UC-II '40')."""
    rng = _norm(entry.get("typical_dosing_range"))
    m = re.match(r"^\s*([0-9.]+)\s*[-–]\s*([0-9.]+)", rng)
    if m:
        return float(m.group(1)), float(m.group(2))
    m1 = re.match(r"^\s*([0-9.]+)\s*$", rng)
    if m1:
        v = float(m1.group(1))
        return v, v
    return None


def _range_mg(entry: Dict[str, Any]) -> Optional[tuple]:
    """Parsed dosing range converted to mg. Entries may be grams (peptides,
    gelatin) or mg (UC-II, BioCell, NEM); masses come back from _mass_mg in mg,
    so the range must be unit-matched before comparison."""
    rng = _parse_dose_range(entry)
    if rng is None:
        return None
    factor = 1000.0 if _norm(entry.get("unit")) in {"g", "gram", "grams"} else 1.0
    return rng[0] * factor, rng[1] * factor


def score_collagen_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Collagen dose adapter via the per-subtype clinical range. Never returns None
    (a primary collagen with no dose is 0, not denominator-excluded)."""
    row = _primary_collagen_active(product)
    if row is None:
        return {"score": 0.0, "band": "no_collagen_active", "metadata": {}}

    if row.get("is_blend_header") or row.get("blend_total_weight_only") or row.get("is_parent_total"):
        return {"score": 7.0, "band": "blend_total_only", "metadata": {}}
    # anchor / product-level total is not a verified per-ingredient dose
    if (row.get("scoring_input_kind") == "product_level_evidence"
            or row.get("evidence_type") == "blend_anchor_mass"):
        return {"score": 7.0, "band": "blend_total_only", "metadata": {}}

    mass = _mass_mg(row)
    if mass is None:
        return {"score": 0.0, "band": "primary_no_dose", "metadata": {}}

    entry = _collagen_dosing_entry(row, product)
    rng = _range_mg(entry) if entry else None
    if rng is None:
        return {"score": 10.0, "band": "disclosed_no_reference", "metadata": {}}

    lo, hi = rng
    meta = {"dose_mg": mass, "range_mg": [lo, hi]}
    if lo <= mass <= hi:
        return {"score": 21.0, "band": "within_studied_range", "metadata": meta}
    if 0.8 * lo <= mass < lo or hi < mass <= 1.2 * hi:
        return {"score": 16.0, "band": "near_studied_range", "metadata": meta}
    if mass < 0.8 * lo:
        return {"score": 10.0, "band": "below_studied_range", "metadata": meta}
    return {"score": 12.0, "band": "above_studied_range", "metadata": meta}


def score_collagen_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Collagen formulation adapter (max 15). Replaces A1/A2 for collagen."""
    row = _primary_collagen_active(product)
    if row is None:
        return {"score": 0.0, "max": COLLAGEN_FORMULATION_CAP, "components": {},
                "metadata": {"reason": "no_collagen_active"}}

    text = _identity_text(row)
    components: Dict[str, float] = {"recognized_collagen_identity": 6.0}
    if any(t in text for t in _HYDROLYZED_TOKENS):
        components["hydrolyzed_peptides"] = 2.0
    if _TYPE_RE.search(text):
        components["type_disclosed"] = 3.0
    if any(t in text for t in _SOURCE_TOKENS):
        components["source_disclosed"] = 2.0
    if _mass_mg(row) is not None:
        components["quantified_dose_present"] = 2.0
    if any(b in text for b in _COLLAGEN_BRANDS):
        components["branded_clinically_studied"] = 3.0

    raw = sum(components.values())
    return {"score": round(min(COLLAGEN_FORMULATION_CAP, max(0.0, raw)), 4),
            "max": COLLAGEN_FORMULATION_CAP, "components": components,
            "metadata": {"recognized": True, "raw": round(raw, 4),
                         "cap_applied": raw > COLLAGEN_FORMULATION_CAP}}
