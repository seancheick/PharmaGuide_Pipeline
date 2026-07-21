"""Pipeline-authored pillar explanation facts.

A pure adapter that turns module-breakdown metadata the scorer already computed
into small, versioned, consumer-facing "facts" that explain a pillar. It never
recomputes a score, never mutates ``score``/``max``/``reason``, and never
generates prose — it only attaches an optional ``explanation`` block to a
pillar. New fact sources are added here, not in the scorer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PILLAR_EXPLANATION_SCHEMA_VERSION = 1

# Internal omega molecular-form codes (omega_formulation._detect_form) -> the
# consumer copy shown on the score card. "undefined" is intentionally absent so
# an undisclosed form emits no fact rather than a guess.
_OMEGA_FORM_COPY = {
    "tg": "Triglyceride",
    "rtg": "Re-esterified triglyceride",
    "pl": "Phospholipid",
    "ee": "Ethyl ester",
}


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_mg_per_day(value: float) -> str:
    return f"{int(round(value))} mg/day"


def _nonnegative_int(value: Any) -> Optional[int]:
    if type(value) is not int or value < 0:
        return None
    return value


def _omega_dose_facts(dose_dim: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = dose_dim.get("metadata") if isinstance(dose_dim, dict) else None
    per_day = _num((metadata or {}).get("per_day_mid_mg"))
    if per_day is None or per_day <= 0:
        return []
    return [
        {
            "id": "epa_dha_per_day",
            "label": "EPA + DHA per day",
            "value_mg": round(per_day, 1),
            "value_display": _format_mg_per_day(per_day),
        }
    ]


def _omega_formulation_facts(formulation_dim: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = formulation_dim.get("metadata") if isinstance(formulation_dim, dict) else None
    code = str((metadata or {}).get("form_detected") or "").strip().lower()
    display = _OMEGA_FORM_COPY.get(code)
    if not display:
        return []
    return [
        {
            "id": "omega_form",
            "label": "Molecular form",
            "value": code,
            "value_display": display,
        }
    ]


def _proprietary_blend_facts(transparency_dim: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = transparency_dim.get("metadata") if isinstance(transparency_dim, dict) else None
    evidence = metadata.get("B5_blend_evidence") if isinstance(metadata, dict) else None
    if not isinstance(evidence, list) or not evidence:
        return []

    hidden_count = 0
    for entry in evidence:
        if not isinstance(entry, dict):
            return []
        count = _nonnegative_int(entry.get("children_without_amount_count"))
        if count is None:
            return []
        hidden_count += count

    return [
        {
            "id": "proprietary_blend_count",
            "label": "Proprietary blends",
            "value_display": str(len(evidence)),
        },
        {
            "id": "undisclosed_ingredient_amount_count",
            "label": "Ingredient amounts not disclosed",
            "value_display": str(hidden_count),
        },
    ]


def _zero_evidence_facts(
    pillar: Dict[str, Any], evidence_dim: Dict[str, Any]
) -> List[Dict[str, Any]]:
    if _num(pillar.get("score")) != 0:
        return []
    metadata = evidence_dim.get("metadata") if isinstance(evidence_dim, dict) else None
    matched_entries = metadata.get("matched_entries") if isinstance(metadata, dict) else None
    if type(matched_entries) is not int or matched_entries != 0:
        return []
    return [
        {
            "id": "matched_evidence_records",
            "label": "Qualifying evidence matches",
            "value_display": "0 in PharmaGuide's current evidence data",
        }
    ]


# Fact builders keyed by the pillar assembler that owns them. Adding a new
# fact-bearing pillar is a one-line entry here.
_FACT_BUILDERS = {
    "dose": _omega_dose_facts,
    "formulation": _omega_formulation_facts,
}


def attach_pillar_explanations(
    pillars: Dict[str, Any],
    module_bd: Dict[str, Any],
    cfg: Dict[str, Any],
    module: Optional[str],
) -> Dict[str, Any]:
    """Attach optional ``explanation`` blocks to ``pillars`` in place.

    Returns ``pillars`` for convenience. Facts are built only from the module
    breakdown metadata the scorer already produced; absent inputs emit no fact.
    """
    dims = (module_bd or {}).get("dimensions") or {}
    specs = (cfg or {}).get("pillars") or {}
    dim_by_assembler = {"dose": dims.get("dose") or {}, "formulation": dims.get("formulation") or {}}

    for name, spec in specs.items():
        pillar = pillars.get(name)
        if not isinstance(pillar, dict):
            continue
        assembler = spec.get("assembler")
        facts: List[Dict[str, Any]] = []
        builder = _FACT_BUILDERS.get(assembler) if module == "omega" else None
        if builder is not None:
            facts.extend(builder(dim_by_assembler.get(assembler) or {}))
        if assembler == "evidence":
            facts.extend(_zero_evidence_facts(pillar, dims.get("evidence") or {}))
        if spec.get("source_dim") == "transparency":
            facts.extend(_proprietary_blend_facts(dims.get("transparency") or {}))
        if facts:
            pillar["explanation"] = {
                "schema_version": PILLAR_EXPLANATION_SCHEMA_VERSION,
                "facts": facts,
            }
    return pillars
