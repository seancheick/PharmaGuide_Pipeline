"""Shared scoring reference resolver (ScoringClassification v1 support).

Single source of truth for "what dose/quality reference family applies to an
ingredient." Consumed by BOTH the scoring-classification contract
(``scoring_input_contract.py``) and the scorer (``generic_dose`` /
``botanical_profile``).

Dependency rule (advisor non-negotiable #1): this module imports NOTHING from
the scorer or the contract. It reads data files only. That keeps the dependency
direction one-way::

    scoring_input_contract  ->  scoring_reference_resolver  <-  scoring_v4 scorer

so the contract never depends on scoring-adapter internals.

A *reference family* is "what kind of dose-adequacy question applies":

==================== =============================== ==========================
family               applies to                      reference source
==================== =============================== ==========================
rda_ul               vitamin / mineral               RDA / AI / UL
botanical_therapeutic herb / standardized botanical   studied clinical range
collagen             collagen subtype                collagen clinical range
omega                EPA / DHA                        intake target
sports               protein / creatine / etc.        sports dose
probiotic            strain                           CFU
unknown              nothing applicable               --
==================== =============================== ==========================

``reference_family()`` returns a structured :class:`ReferenceResult` so callers
can *explain and audit* the decision (matched id / alias / source / confidence /
reason_code), not just branch on a bare string.

IMPORTANT: ``rda_therapeutic_dosing.json`` membership is **evidence, not
ownership**. A product can contain a small botanical that has a therapeutic
reference without being a botanical product. Ownership (``owner_type``) is
decided in the contract by combining this evidence with role + materiality +
intent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = Path(__file__).resolve().parent / "data"
_THERAPEUTIC_PATH = _DATA_DIR / "rda_therapeutic_dosing.json"
_RDA_UL_PATH = _DATA_DIR / "rda_optimal_uls.json"
_BOTANICAL_IDENTITY_PATH = _DATA_DIR / "botanical_ingredients.json"

# Domain (as stamped by the contract's _ingredient_domain) -> reference family.
_DOMAIN_FAMILY: Dict[str, str] = {
    "vitamin": "rda_ul",
    "mineral": "rda_ul",
    "omega_epa_dha": "omega",
    "omega_parent": "omega",
    "sports_active": "sports",
    "probiotic_strain": "probiotic",
    "collagen": "collagen",
    "herb": "botanical_therapeutic",
    "botanical_marker": "botanical_therapeutic",
}

REFERENCE_FAMILIES = frozenset({
    "rda_ul", "botanical_therapeutic", "collagen", "omega", "sports", "probiotic", "unknown",
})


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _identity_keys(canonical_id: Any, name: Any, aliases: Any) -> List[str]:
    keys = [_norm(canonical_id), _norm(name)]
    if isinstance(aliases, (list, tuple, set)):
        keys.extend(_norm(a) for a in aliases)
    elif aliases:
        keys.append(_norm(aliases))
    out: List[str] = []
    for k in keys:
        if k and k not in out:
            out.append(k)
    return out


@lru_cache(maxsize=1)
def _therapeutic_index() -> Dict[str, Dict[str, Any]]:
    """normalized id / standard_name / alias -> therapeutic dosing entry.

    Faithful replica of ``botanical_profile._dosing_index`` so the resolver and
    the scorer agree on therapeutic-reference membership (parity-tested)."""
    try:
        raw = json.loads(_THERAPEUTIC_PATH.read_text())
    except Exception:  # pragma: no cover - missing data degrades to empty
        return {}
    index: Dict[str, Dict[str, Any]] = {}
    for entry in raw.get("therapeutic_dosing", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("id"), entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                index.setdefault(k, entry)
    return index


@lru_cache(maxsize=1)
def _rda_ul_index() -> Dict[str, Dict[str, Any]]:
    try:
        raw = json.loads(_RDA_UL_PATH.read_text())
    except Exception:  # pragma: no cover
        return {}
    index: Dict[str, Dict[str, Any]] = {}
    for entry in raw.get("nutrient_recommendations", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("id"), entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                index.setdefault(k, entry)
    return index


@dataclass(frozen=True)
class ReferenceResult:
    family: str
    matched_reference_id: Optional[str] = None
    matched_alias: Optional[str] = None
    confidence: str = "low"  # high | medium | low
    reason_code: str = ""
    source_path: Optional[str] = None


def _lookup(index: Dict[str, Dict[str, Any]], keys: List[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    for k in keys:
        entry = index.get(k)
        if entry is not None:
            return entry, k
    return None, None


@lru_cache(maxsize=1)
def _botanical_identity_index() -> frozenset:
    """Normalized id/standard_name/alias set of genuine botanicals
    (botanical_ingredients.json). Used to confirm a row is really a botanical —
    membership in standardized_botanicals.json alone is NOT proof (it contains
    non-botanical branded compounds, e.g. Setria glutathione)."""
    try:
        raw = json.loads(_BOTANICAL_IDENTITY_PATH.read_text())
    except Exception:  # pragma: no cover
        return frozenset()
    names: set = set()
    for entry in raw.get("botanical_ingredients", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("id"), entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                names.add(k)
    return frozenset(names)


def is_known_botanical(canonical_id: Any = None, name: Any = None, aliases: Any = None) -> bool:
    """True when the identity matches a genuine botanical in
    botanical_ingredients.json."""
    index = _botanical_identity_index()
    return any(k in index for k in _identity_keys(canonical_id, name, aliases))


def has_therapeutic_reference(canonical_id: Any = None, name: Any = None, aliases: Any = None) -> bool:
    """True when the ingredient matches a ``rda_therapeutic_dosing`` entry.

    EVIDENCE of a clinical botanical/collagen dose range — NOT proof of
    botanical ownership (role + materiality + intent must also agree)."""
    entry, _alias = _lookup(_therapeutic_index(), _identity_keys(canonical_id, name, aliases))
    return entry is not None


def reference_family(
    canonical_id: Any = None,
    name: Any = None,
    aliases: Any = None,
    domain: Any = None,
) -> ReferenceResult:
    """Resolve an ingredient's dose-reference family as a structured result."""
    keys = _identity_keys(canonical_id, name, aliases)
    family = _DOMAIN_FAMILY.get(_norm(domain), "unknown")

    if family in ("botanical_therapeutic", "collagen"):
        entry, alias = _lookup(_therapeutic_index(), keys)
        if entry is not None:
            return ReferenceResult(
                family=family,
                matched_reference_id=entry.get("id") or entry.get("standard_name"),
                matched_alias=alias,
                confidence="high",
                reason_code="therapeutic_reference_matched",
                source_path="data/rda_therapeutic_dosing.json",
            )
        return ReferenceResult(
            family=family,
            confidence="low",
            reason_code="no_therapeutic_reference",
            source_path="data/rda_therapeutic_dosing.json",
        )

    if family == "rda_ul":
        entry, alias = _lookup(_rda_ul_index(), keys)
        if entry is not None:
            return ReferenceResult(
                family="rda_ul",
                matched_reference_id=entry.get("id") or entry.get("standard_name"),
                matched_alias=alias,
                confidence="high",
                reason_code="rda_ul_reference_matched",
                source_path="data/rda_optimal_uls.json",
            )
        return ReferenceResult(
            family="rda_ul",
            confidence="medium",
            reason_code="rda_ul_by_domain_no_exact_match",
            source_path="data/rda_optimal_uls.json",
        )

    if family in ("omega", "sports", "probiotic"):
        return ReferenceResult(family=family, confidence="medium", reason_code=f"{family}_by_domain")

    return ReferenceResult(family="unknown", confidence="low", reason_code="no_reference_family")
