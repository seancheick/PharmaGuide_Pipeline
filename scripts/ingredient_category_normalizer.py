"""Ingredient-category canonicalization (SP-4, 2026-05-21).

Single normalization stage for the per-ingredient `category` field. Reads
`scripts/data/ingredient_category_vocab.json` as the source of truth and
emits one of the 17 canonical IDs (see `INGREDIENT_CATEGORY_IDS`).

Public surface:
    canonicalize_ingredient_category(value) -> str
    INGREDIENT_CATEGORY_IDS  — frozenset of canonical IDs from the vocab JSON
    INGREDIENT_CATEGORY_UNKNOWN = ""  — empty-string sentinel for missing data

Layer contract (per SP-0 design doc): answers WHAT an ingredient is.
Distinct from:
  - functional_role (WHY it is in the product) — SP-5
  - safety_role (whether it affects safety gates) — banned_status / clinical_risk
  - ingredient_identity (WHO it is) — canonical_id / IQM parent key

Owned by the enricher. Replaces the hardcoded CATEGORY_ALIASES map in
`supplement_type_utils.py` (the legacy function `canonical_category()`
remains as a backward-compatible wrapper that calls into this normalizer).

Returns the canonical id when an alias matches; returns the original
normalized string when no alias matches (lets unusual values pass through
unchanged so the taxonomy classifier can still reason about them). This
intentionally differs from form_factor_normalizer's `unknown` sentinel
because ingredient categories have a long tail of edge values and
silently dropping unknown ones into a sentinel would hide drift.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict


_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "data", "ingredient_category_vocab.json")
_LOGGER = logging.getLogger(__name__)

# Hardcoded fallback — kept in sync with the JSON vocab by
# `test_ingredient_category_vocab.py::TestVocabSync`. Order matches JSON.
_FALLBACK_IDS = (
    "vitamin",
    "mineral",
    "herb",
    "botanical",
    "antioxidant",
    "fatty_acid",
    "amino_acid",
    "probiotic",
    "bacteria",
    "protein",
    "fiber",
    "enzyme",
    "functional_food",
    "delivery",
    "additive",
    "inactive",
    "other",
)

INGREDIENT_CATEGORY_UNKNOWN = ""


def _normalize_text(value: Any) -> str:
    """Lowercase, strip, replace dashes/spaces/punctuation with single
    underscores. Mirrors supplement_type_utils.canonical_category() input
    normalization so existing call sites get identical canonicalization."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    # Replace common separators with underscore; keep alnum+underscore.
    text = re.sub(r"[-\s\.\/\\,;:|()\[\]{}]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


@lru_cache(maxsize=1)
def _load_vocab() -> Dict[str, Any]:
    """Load the vocab JSON. Returns a dict with entries + alias_index for
    fast lookup. Falls back to a hardcoded list if the JSON is missing or
    invalid so the pipeline can still start."""
    try:
        with open(_VOCAB_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("ingredient_categories", [])
        if not isinstance(entries, list) or not entries:
            raise ValueError("ingredient_categories array empty or malformed")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        _LOGGER.warning(
            "ingredient_category_vocab.json unavailable (%s); using hardcoded fallback",
            exc,
        )
        entries = [
            {"id": fid, "aliases": [fid.replace("_", " "), fid]} for fid in _FALLBACK_IDS
        ]

    alias_index: Dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fid = str(entry.get("id") or "").strip().lower()
        if not fid:
            continue
        # The canonical id itself is always a valid alias.
        alias_index.setdefault(fid, fid)
        for alias in entry.get("aliases", []) or []:
            norm = _normalize_text(alias)
            if norm:
                alias_index.setdefault(norm, fid)

    return {"entries": entries, "alias_index": alias_index}


def _canonical_ids() -> frozenset[str]:
    return frozenset(
        str(e.get("id") or "").strip().lower()
        for e in _load_vocab()["entries"]
        if isinstance(e, dict) and e.get("id")
    )


# Public attribute — recomputed on each access so test-time vocab edits
# pick up after `_load_vocab.cache_clear()`.
def __getattr__(name: str):
    if name == "INGREDIENT_CATEGORY_IDS":
        return _canonical_ids()
    raise AttributeError(name)


def canonicalize_ingredient_category(value: Any) -> str:
    """Map a raw ingredient-category string to one of the canonical vocab IDs.

    Matching order:
      1. Exact alias match against the normalized input.
      2. Fall-through — return the normalized input unchanged so unusual
         edge values (e.g. `section_other`, `blend_header`) can still
         flow through downstream consumers without losing the original
         signal. Unlike form_factor's `unknown` sentinel, ingredient
         category has a long tail of legitimate edge values, so silent
         coercion would hide drift.

    Returns a string. Never None. Empty input → empty string sentinel.
    """
    text = _normalize_text(value)
    if not text:
        return INGREDIENT_CATEGORY_UNKNOWN
    vocab = _load_vocab()
    return vocab["alias_index"].get(text, text)
