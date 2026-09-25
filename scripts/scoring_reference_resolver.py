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
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = Path(__file__).resolve().parent / "data"
_THERAPEUTIC_PATH = _DATA_DIR / "rda_therapeutic_dosing.json"
_RDA_UL_PATH = _DATA_DIR / "rda_optimal_uls.json"
_BOTANICAL_IDENTITY_PATH = _DATA_DIR / "botanical_ingredients.json"
_IQM_PATH = _DATA_DIR / "ingredient_quality_map.json"

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


@lru_cache(maxsize=1)
def iqm_reference_index() -> Dict[str, Dict[str, Any]]:
    """Canonical IQM id -> entry for cross-layer identity decisions.

    This dependency-free resolver owns this cross-layer reference lookup;
    neither enrichment measurements nor the scoring contract should import the
    other merely to ask what category an already-resolved canonical id owns.
    """
    try:
        raw = json.loads(_IQM_PATH.read_text())
    except Exception:  # pragma: no cover - missing data degrades to empty
        return {}
    return {
        _norm(key): value
        for key, value in raw.items()
        if key != "_metadata" and isinstance(value, dict)
    }


def iqm_reference_entry(canonical_id: Any) -> Optional[Dict[str, Any]]:
    """Return the exact IQM entry for a canonical id, without alias guessing."""
    key = _norm(canonical_id)
    return iqm_reference_index().get(key) if key else None


_LOW_CONFIDENCE_REVIEW_STATUSES = frozenset({"stub", "pending", "needs_review"})
_UNKNOWN_FORM_TOKENS = ("unspecified", "unknown", "generic", "default")
_EXACT_UNSPECIFIED_RE = re.compile(r"\(unspecified\)\s*$", re.IGNORECASE)
UNKNOWN_FORM_NAME = "unspecified"


# Why a form cannot define the nondisclosure floor (IQM form field
# ``unknown_floor: {"eligible": false, "reason": ...}``). Absent = eligible.
UNKNOWN_FLOOR_INELIGIBLE_REASONS = frozenset({
    "non_functional_analog",
    "degradation_product",
    "wrong_stereoisomer",
    "different_compound",
    "not_a_nutrient_source",
})
# A reviewed override lets an authored unspecified form sit above the floor:
# ``unknown_floor: {"override": true, "rationale", "reviewed_by", "reviewed_on"}``.
UNKNOWN_FLOOR_OVERRIDE_FIELDS = ("rationale", "reviewed_by", "reviewed_on")


def _raw_form_bio(parent: Dict[str, Any], form: Dict[str, Any]) -> Optional[float]:
    try:
        bio = float(form.get("bio_score"))
    except (TypeError, ValueError):
        return None
    review = str((parent.get("data_quality") or {}).get("review_status", "")).strip().lower()
    return min(bio, 10.0) if review in _LOW_CONFIDENCE_REVIEW_STATUSES else bio


def _candidate_forms(parent: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    # A named source preparation is never an identity-neutral default.
    return {
        name: form for name, form in (parent.get("forms") or {}).items()
        if isinstance(form, dict)
        and form.get("alias_identity_scope") != "source_preparation"
        and _raw_form_bio(parent, form) is not None
    }


def floor_eligible(form: Dict[str, Any]) -> bool:
    """Whether a named form may define the nondisclosure floor."""
    return (form.get("unknown_floor") or {}).get("eligible", True) is not False


def unknown_floor_override(form: Dict[str, Any]) -> bool:
    """A complete reviewed override on an authored unspecified form."""
    floor = form.get("unknown_floor") or {}
    return floor.get("override") is True and all(
        str(floor.get(field) or "").strip() for field in UNKNOWN_FLOOR_OVERRIDE_FIELDS
    )


def authored_unknown_form(parent: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """The parent's authored unspecified form, chosen deterministically: the
    exact "(unspecified)" form (vitamin D: 'vitamin d (unspecified)', never
    'vitamin D2 (unspecified source)'), else a form named unspecified/unknown/
    generic/default. None when IQM authored none."""
    forms = _candidate_forms(parent)
    exact = sorted(n for n in forms if _EXACT_UNSPECIFIED_RE.search(n))
    if exact:
        return exact[0], forms[exact[0]]
    for token in _UNKNOWN_FORM_TOKENS:
        named = sorted(n for n in forms if token in n.lower())
        if named:
            return named[0], forms[named[0]]
    return None


def unknown_floor(parent: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    """``(lowest eligible named bio_score - 1, that form's name)``, floored at 0;
    None when no named form is eligible."""
    authored = authored_unknown_form(parent)
    named = sorted(
        (_raw_form_bio(parent, form), name)
        for name, form in _candidate_forms(parent).items()
        if (not authored or name != authored[0]) and floor_eligible(form)
    )
    if not named:
        return None
    return max(0.0, named[0][0] - 1.0), named[0][1]


def unknown_form_quality(parent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """What a form the label does not disclose is worth under this parent:
    the lowest eligible named bio_score minus 1, so nondisclosure never
    scores above the plainest real form.

    - An authored unspecified form supplies the identity. Its own bio_score
      counts only at or below that floor, or above it with a reviewed
      override (``unknown_floor_override``).
    - With no authored form the result is identity-neutral: ``form_id`` is
      None, so no named form's aliases, absorption, notes, identifiers,
      evidence or consumer copy can attach to it.

    Only genuine nondisclosure belongs here. A named form IQM does not
    recognize stays unmapped for curation, and a disclosed form the pipeline
    lost is a pipeline defect; neither should be routed to this value.
    """
    authored = authored_unknown_form(parent)
    floor = unknown_floor(parent)
    if authored:
        authored_bio = _raw_form_bio(parent, authored[1])
        if floor is None or unknown_floor_override(authored[1]) or authored_bio <= floor[0]:
            bio, basis = authored_bio, "authored_unspecified"
        else:
            bio, basis = floor[0], "authored_capped_at_floor"
        return {"form_id": authored[0], "form": authored[1], "bio_score": bio, "basis": basis}
    if floor is None:
        return None
    return {"form_id": None, "form": None, "bio_score": floor[0],
            "basis": "derived_lowest_eligible_minus_one"}


def effective_form_bio(parent: Dict[str, Any], form: Dict[str, Any]) -> Optional[float]:
    """The one form-quality value: IQM ``bio_score``, capped at 10 while the
    parent's review is provisional; the parent's authored unspecified form is
    worth ``unknown_form_quality``. None when the form carries no bio_score."""
    bio = _raw_form_bio(parent, form)
    if bio is None:
        return None
    authored = authored_unknown_form(parent)
    if authored and (authored[1] is form or authored[1] == form):
        return unknown_form_quality(parent)["bio_score"]
    return bio


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


def rda_ul_reference_entry(
    canonical_id: Any = None,
    name: Any = None,
    aliases: Any = None,
) -> Optional[Dict[str, Any]]:
    """Return the exact RDA/UL nutrition authority entry for an ingredient via canonical keys/aliases."""
    entry, _ = _lookup(_rda_ul_index(), _identity_keys(canonical_id, name, aliases))
    return entry


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
