"""Form-keyword vocabulary loader.

Single source of truth for every form-keyword regex used across the
pipeline. Replaces the 3-5 hardcoded keyword lists previously scattered
across enhanced_normalizer.py, score_supplements.py, enrich_supplements_v3.py,
and constants.py.

Loaded once at import time; regexes compiled once. Pure functions on a
frozen module-level singleton — no mutable state.

Three consumer surfaces:

  extract_forms(text, categories=None)
      Cleaner usage. Walk the named categories (or all) and return the
      ordered list of canonical form names that match the text.

  matches_premium_omega3_form(haystack)
      Scorer usage. Boolean — does the text disclose a premium omega-3
      molecular form? Used to gate the A2 bonus in score_supplements.

  matches_probiotic_delivery(text)
  matches_postbiotic(text)
      Enricher usage. Booleans — does the text disclose a probiotic
      delivery technology / postbiotic carrier? Used in
      enrich_supplements_v3 for survivability + CFU-gate decisions.

Source data: scripts/data/form_keywords_vocab.json
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Pattern, Tuple

_VOCAB_PATH = Path(__file__).parent / "data" / "form_keywords_vocab.json"


@dataclass(frozen=True)
class _Form:
    canonical: str
    patterns: Tuple[Pattern[str], ...]


@dataclass(frozen=True)
class _Category:
    id: str
    description: str
    scoring_relevance: str
    exclusive_match: bool  # True = stop after first canonical matches
    forms: Tuple[_Form, ...]


def _load() -> Tuple[Tuple[_Category, ...], dict]:
    with _VOCAB_PATH.open() as f:
        raw = json.load(f)
    categories = []
    for cat_id, cat_data in raw.get("categories", {}).items():
        forms = tuple(
            _Form(
                canonical=entry["canonical"],
                patterns=tuple(
                    re.compile(p, re.IGNORECASE) for p in entry["patterns"]
                ),
            )
            for entry in cat_data.get("forms", [])
        )
        categories.append(
            _Category(
                id=cat_id,
                description=cat_data.get("description", ""),
                scoring_relevance=cat_data.get("scoring_relevance", ""),
                exclusive_match=bool(cat_data.get("exclusive_match", False)),
                forms=forms,
            )
        )
    return tuple(categories), raw.get("_metadata", {})


_CATEGORIES, _METADATA = _load()
_BY_ID = {c.id: c for c in _CATEGORIES}


# Public introspection ----------------------------------------------------

def metadata() -> dict:
    """Return vocab metadata block."""
    return dict(_METADATA)


def category_ids() -> Tuple[str, ...]:
    return tuple(_BY_ID.keys())


def canonicals_in(category_id: str) -> Tuple[str, ...]:
    """Return the ordered tuple of canonical form names in a category."""
    cat = _BY_ID.get(category_id)
    return tuple(f.canonical for f in cat.forms) if cat else ()


# Cleaner surface ---------------------------------------------------------

def extract_forms(text: str, categories: Optional[Iterable[str]] = None) -> List[str]:
    """Return the ordered list of canonical form names matched in text.

    Walks each category in declaration order. Within a category, walks
    forms in declaration order so more specific patterns
    ('re-esterified triglyceride') match before less specific ones
    ('triglyceride'). Each canonical name is reported at most once.

    Args:
        text: Raw ingredient name to scan.
        categories: Iterable of category ids to search. None = all.

    Returns:
        List of canonical form names, in match order, deduplicated.
    """
    if not text:
        return []
    seen: set[str] = set()
    out: List[str] = []
    target_cats = (
        [_BY_ID[c] for c in categories if c in _BY_ID]
        if categories is not None
        else _CATEGORIES
    )
    for cat in target_cats:
        category_emitted = False
        for form in cat.forms:
            if form.canonical in seen:
                continue
            for pattern in form.patterns:
                if pattern.search(text):
                    seen.add(form.canonical)
                    out.append(form.canonical)
                    category_emitted = True
                    break
            # Categories marked exclusive_match emit only the first
            # canonical that matches. Used for mutually-exclusive
            # form groups (e.g. folate active vs synthetic — a label
            # saying "L-5-MTHF, not folic acid" must not also emit
            # folic acid).
            if category_emitted and cat.exclusive_match:
                break
    return out


# Scorer surface ---------------------------------------------------------

def matches_premium_omega3_form(haystack: str) -> bool:
    """True if the text discloses a premium-form omega-3 molecular form.

    Replaces score_supplements._PREMIUM_OMEGA3_FORM_PATTERN. Reads the
    omega3_molecular_forms category — every canonical form there gates
    the A2 bonus. The scorer doesn't care which specific form matched,
    only that one did.
    """
    if not haystack:
        return False
    cat = _BY_ID.get("omega3_molecular_forms")
    if not cat:
        return False
    for form in cat.forms:
        for pattern in form.patterns:
            if pattern.search(haystack):
                return True
    return False


# Enricher surface -------------------------------------------------------

def matches_probiotic_delivery(text: str) -> bool:
    """True if the text discloses a probiotic delivery technology
    (spore-based / microencapsulated / acid-resistant / delayed-release /
    enteric-coated). Used by the enricher's survivability scoring.
    """
    return _category_matches(text, "probiotic_delivery")


def matches_postbiotic(text: str) -> bool:
    """True if the text indicates the strain is non-viable (postbiotic /
    heat-killed / tyndallized / lysate / inactivated). Used by the
    enricher's CFU hard-gate — postbiotics receive no CFU credit.
    """
    return _category_matches(text, "postbiotic_keywords")


def _category_matches(text: str, category_id: str) -> bool:
    if not text:
        return False
    cat = _BY_ID.get(category_id)
    if not cat:
        return False
    for form in cat.forms:
        for pattern in form.patterns:
            if pattern.search(text):
                return True
    return False
