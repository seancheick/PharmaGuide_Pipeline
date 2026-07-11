"""Pipeline-authored pillar explanation facts.

A pure adapter that turns module-breakdown metadata the scorer already computed
into small, versioned, consumer-facing "facts" that explain a pillar. It never
recomputes a score, never mutates ``score``/``max``/``reason``, and never
generates prose — it only attaches an optional ``explanation`` block to a
pillar. Only the omega module emits facts today; every other module keeps
reason-only pillars. New fact sources are added here, not in the scorer.
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
            "display": _format_mg_per_day(per_day),
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
            "display": display,
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
    if module != "omega":
        return pillars

    dims = (module_bd or {}).get("dimensions") or {}
    specs = (cfg or {}).get("pillars") or {}
    dim_by_assembler = {"dose": dims.get("dose") or {}, "formulation": dims.get("formulation") or {}}

    for name, spec in specs.items():
        pillar = pillars.get(name)
        if not isinstance(pillar, dict):
            continue
        builder = _FACT_BUILDERS.get(spec.get("assembler"))
        if builder is None:
            continue
        facts = builder(dim_by_assembler.get(spec.get("assembler")) or {})
        if facts:
            pillar["explanation"] = {
                "schema_version": PILLAR_EXPLANATION_SCHEMA_VERSION,
                "facts": facts,
            }
    return pillars
