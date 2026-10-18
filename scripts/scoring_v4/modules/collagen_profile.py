"""V4 Phase 7 — Collagen Profile (formulation + dose adapters).

Collagen receives its own formulation and Dose assessments. Mass-dominance
routing keeps a multivitamin with an incidental collagen row on its existing
route. Exact subtype identity selects the existing source record.

  Formulation adapter (replaces A1/A2; reference 8), V4.1 Step 4:
    recognized collagen identity         collagen_identity_neutral (neutral baseline)
    hydrolyzed peptides (not gelatin)    collagen_hydrolyzed
  Type, source and the printed amount are Transparency facts; a brand name is
  an Evidence fact.

  Dose adapter: subtype-specific source regimens remain descriptive. Their
  reviewed general benchmark conclusion uses the completed neutral; missing
  amounts and unresolved source/preparation reviews retain their holds.

Reuses the shared identity/mass/dosing helpers from botanical_profile so unit
normalization (incl. DSLD "Gram(s)") and routing stay consistent across profiles.

Spec: docs/superpowers/specs/2026-06-01-v4-collagen-profile-design.md
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from collagen_taxonomy import (
    HYDROLYZED_TYPE_II,
    SUBTYPE_TO_DOSING_ALIAS,
    classify_collagen_subtype,
    classify_collagen_subtype_strict,
)
from scoring_input_contract import (
    ROLE_CLAIM_PROMINENT,
    ROLE_PRIMARY,
    classify_ingredient_roles,
    dose_disclosure_status,
)
from scoring_v4.modules.botanical_profile import (
    unassessed_amount_band,
    _norm,
    _mass_mg,
    _scoring_actives,
    _forms_text,
    _ingredient_identity_keys,
    _dosing_index,
    _classification_profile_eligible,
    _classification_product_profile_eligible,
)

from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "collagen")["collagen"]


COLLAGEN_FORMULATION_CAP = _FVM["collagen_formulation_cap"]
COLLAGEN_IDENTITY_NEUTRAL = _FVM["collagen_identity_neutral"]
COLLAGEN_HYDROLYZED = _FVM["collagen_hydrolyzed"]

_COLLAGEN_TOKENS = ("collagen", "gelatin")
_HYDROLYZED_TOKENS = ("hydrolyzed", "hydrolysed", "hydrolysate", "peptide")


def _identity_text(row: Dict[str, Any]) -> str:
    return _forms_text(row) + " " + " ".join(_ingredient_identity_keys(row))


def _is_collagen_active(row: Dict[str, Any]) -> bool:
    contract_eligible = _classification_profile_eligible(row, "collagen")
    if contract_eligible is not None:
        return contract_eligible
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
    contract_eligible = _classification_product_profile_eligible(product, "collagen")
    if contract_eligible is not None:
        return contract_eligible
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
        row_text = _identity_text(row)
        subtype = classify_collagen_subtype_strict(row_text)
        if subtype is None:
            # Product context may disambiguate a generic row as the explicitly
            # named Type-II preparation. A bare collagen identity does not
            # establish the hydrolyzed-peptide benchmark.
            product_name = product.get("product_name") if isinstance(product, dict) else None
            contextual = classify_collagen_subtype(row_text, product_name)
            if contextual == HYDROLYZED_TYPE_II:
                subtype = contextual
    if subtype not in SUBTYPE_TO_DOSING_ALIAS:
        return None
    return index.get(SUBTYPE_TO_DOSING_ALIAS[subtype])


def _score_collagen_row(row: Dict[str, Any], product: Dict[str, Any]) -> Dict[str, Any]:
    """Use the completed source disposition while retaining amount holds."""
    entry = _collagen_dosing_entry(row, product)
    semantics = (entry or {}).get("reference_semantics") or {}
    completed = (semantics.get("curve") == "completed_no_benchmark_neutral"
                 and str(semantics.get("approval_status") or "").startswith("approved_existing_neutral_"))
    benchmark = "absent" if entry is None or completed else "unresolved"
    if row.get("is_blend_header") or row.get("blend_total_weight_only") or row.get("is_parent_total"):
        return unassessed_amount_band("blend_total_only", benchmark)
    # anchor / product-level total is not a verified per-ingredient dose
    if (row.get("scoring_input_kind") == "product_level_evidence"
            or row.get("evidence_type") == "blend_anchor_mass"):
        return unassessed_amount_band("blend_total_only", benchmark)

    mass = _mass_mg(row)
    if mass is None:
        return unassessed_amount_band("primary_no_dose", benchmark,
                                      label_hidden=dose_disclosure_status(row) == "not_disclosed_blend")
    return unassessed_amount_band("disclosed_no_reference", benchmark)


def score_collagen_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Average each declared collagen preparation's own Dose assessment.

    Incidental collagen rows do not join the denominator. A generic disclosed
    collagen preparation without an exact subtype keeps the established
    limited-assessability credit rather than borrowing the peptide range.
    """
    rows = [row for row in _scoring_actives(product) if _is_collagen_active(row)]
    if not rows:
        return {"score": 0.0, "band": "no_collagen_active", "metadata": {}}

    roles = classify_ingredient_roles(product, rows=rows)
    purpose_rows = [
        row
        for row, role in zip(rows, roles)
        if role.get("role") in {ROLE_PRIMARY, ROLE_CLAIM_PROMINENT}
    ]
    if not purpose_rows:
        purpose_rows = [_primary_collagen_active(product)]
    purpose_rows = [row for row in purpose_rows if isinstance(row, dict)]

    assessments = [_score_collagen_row(row, product) for row in purpose_rows]
    score = sum(float(item["score"]) for item in assessments) / len(assessments)
    bands = [str(item["band"]) for item in assessments]
    band = bands[0] if len(set(bands)) == 1 else "mixed_purpose_average"
    return {
        "score": round(score, 4),
        "band": band,
        "metadata": {
            "purpose_ingredient_count": len(purpose_rows),
            "assessments": [
                {
                    "name": row.get("name") or row.get("standard_name"),
                    "canonical_id": row.get("canonical_id"),
                    "band": assessment["band"],
                    "score": assessment["score"],
                    **assessment.get("metadata", {}),
                }
                for row, assessment in zip(purpose_rows, assessments)
            ],
        },
    }


def score_collagen_purpose_dose(
    product: Dict[str, Any], row: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Assess one declared collagen purpose through the collagen Dose owner."""
    if not _is_collagen_active(row):
        return None
    assessment = _score_collagen_row(row, product)
    return {
        "name": row.get("name") or row.get("standard_name"),
        "canonical_id": row.get("canonical_id"),
        "band": assessment["band"],
        "score": assessment["score"],
        **assessment.get("metadata", {}),
    }


def score_collagen_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Collagen formulation adapter (max 15). Replaces A1/A2 for collagen."""
    row = _primary_collagen_active(product)
    if row is None:
        return {"score": 0.0, "max": COLLAGEN_FORMULATION_CAP, "components": {},
                "metadata": {"reason": "no_collagen_active"}}

    text = _identity_text(row)
    # V4.1 Step 4: identity is a neutral baseline and hydrolysis the earned
    # trait; type, source and amount are Transparency facts, and a brand name
    # is an Evidence fact.
    components: Dict[str, float] = {"recognized_collagen_identity": COLLAGEN_IDENTITY_NEUTRAL}
    if any(t in text for t in _HYDROLYZED_TOKENS):
        components["hydrolyzed_peptides"] = COLLAGEN_HYDROLYZED

    raw = sum(components.values())
    return {"score": round(min(COLLAGEN_FORMULATION_CAP, max(0.0, raw)), 4),
            "max": COLLAGEN_FORMULATION_CAP, "components": components,
            "metadata": {"recognized": True, "raw": round(raw, 4),
                         "cap_applied": raw > COLLAGEN_FORMULATION_CAP}}
