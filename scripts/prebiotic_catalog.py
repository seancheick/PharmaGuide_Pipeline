"""One prebiotic matcher for enrichment and scoring.

The canonical prebiotic identity catalog is ``prebiotics.ingredients`` in
``scripts/data/clinically_relevant_strains.json``.  Both the enricher (display:
``probiotic_data.prebiotic_present`` / ``prebiotic_name`` / ``prebiotic_dose_g``)
and the v4 scorer (the 1-point prebiotic complement) call ``match_prebiotic`` so
a label term cannot be a prebiotic on one side and not the other.

Rules the matcher enforces:

* A catalog standard name or alias matches as a whole phrase inside the label
  text (word boundaries), or exactly.  Nothing else does.
* Generic words (``fiber``, ``dietary fiber``, ``psyllium``) are never a
  prebiotic identity.  A row literally labelled "prebiotic" counts as present
  but with an unresolved identity.
* An alias shared by more than one catalog entry (``human milk oligosaccharide``
  belongs to both 2'-FL and LNnT) marks the row present but ambiguous; the
  matcher never picks one entry for it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent / "data" / "clinically_relevant_strains.json"
GENERIC_PREBIOTIC_LABELS = frozenset({"prebiotic", "prebiotics", "prebiotic blend", "prebiotic fiber", "prebiotic fibre"})
_NON_WORD = re.compile(r"[^a-z0-9']+")


def normalize_prebiotic_text(text: object) -> str:
    return " ".join(_NON_WORD.sub(" ", str(text or "").lower()).split())


@dataclass(frozen=True)
class PrebioticMatch:
    present: bool
    standard_name: str | None  # None when generic or ambiguous
    matched_term: str | None
    ambiguous: bool = False


NO_MATCH = PrebioticMatch(False, None, None)


@lru_cache(maxsize=1)
def prebiotic_catalog() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """((standard_name, (normalized terms...)), ...) straight from the registry."""
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = (payload.get("prebiotics") or {}).get("ingredients") or []
    catalog = []
    for row in rows:
        name = str(row.get("standard_name") or "").strip()
        if not name:
            continue
        terms = {normalize_prebiotic_text(name)}
        terms.update(normalize_prebiotic_text(a) for a in row.get("aliases", []) if str(a).strip())
        catalog.append((name, tuple(sorted(t for t in terms if t))))
    return tuple(catalog)


@lru_cache(maxsize=1)
def _term_index() -> dict[str, tuple[str, ...]]:
    """normalized term -> standard names that declare it (len > 1 == ambiguous alias)."""
    index: dict[str, list[str]] = {}
    for name, terms in prebiotic_catalog():
        for term in terms:
            index.setdefault(term, []).append(name)
    return {term: tuple(names) for term, names in index.items()}


def match_prebiotic(text: object) -> PrebioticMatch:
    norm = normalize_prebiotic_text(text)
    if not norm:
        return NO_MATCH
    hits: list[tuple[int, int, str, tuple[str, ...]]] = []  # (exact, len, term, names)
    for term, names in _term_index().items():
        if norm == term:
            hits.append((1, len(term), term, names))
        elif re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", norm):
            hits.append((0, len(term), term, names))
    if hits:
        hits.sort(reverse=True)
        exact, _, term, names = hits[0]
        if len(names) == 1:
            return PrebioticMatch(True, names[0], term)
        # Ambiguous alias wins only if no unambiguous term also matched.
        for _, _, other_term, other_names in hits:
            if len(other_names) == 1:
                return PrebioticMatch(True, other_names[0], other_term)
        return PrebioticMatch(True, None, term, ambiguous=True)
    if norm in GENERIC_PREBIOTIC_LABELS or re.search(r"(?<![a-z0-9])prebiotics?(?![a-z0-9])", norm):
        return PrebioticMatch(True, None, "prebiotic")
    return NO_MATCH


def row_quantity_g(row: dict) -> float | None:
    """Grams for an ingredient row; None when no mass quantity is disclosed."""
    quantity = None
    for key in ("quantity", "amount", "dose", "dosage"):
        raw = row.get(key)
        if raw is None or isinstance(raw, bool):
            continue
        try:
            quantity = float(raw)
        except (TypeError, ValueError):
            continue
        break
    if quantity is None:
        return None
    unit = str(row.get("unit_normalized") or row.get("unit") or row.get("dose_unit") or "").strip().lower()
    if unit in {"g", "gram", "grams", "gm"}:
        return quantity
    if unit in {"mg", "milligram", "milligrams"}:
        return quantity / 1000.0
    if unit in {"mcg", "microgram", "micrograms", "ug", "µg"}:
        return quantity / 1_000_000.0
    return None
