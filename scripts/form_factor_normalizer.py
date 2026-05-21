"""Form-factor canonicalization (SP-3, 2026-05-21).

Single normalization stage for product physical state. Reads
`scripts/data/form_factor_vocab.json` as the source of truth and emits one
of the canonical IDs (see `FORM_FACTOR_IDS`).

Public surface:
    canonicalize_form_factor(value, *, langual_code=None) -> str
    FORM_FACTOR_IDS  — frozenset of canonical IDs from the vocab JSON
    FORM_FACTOR_UNKNOWN = "unknown"  — explicit no-data sentinel

Owned by the enricher. v4 router/modules, score_supplements, build_final_db,
and Flutter all consume the canonical ID via the `form_factor_canonical`
field on the enriched product blob — they should NOT re-derive from raw text.

The vocab file is the canonical source. If the JSON disappears or is
invalid, the loader logs a warning and falls back to a hardcoded list so
the rest of the pipeline does not crash. The vocab-sync test
(`test_form_factor_vocab.py::TestVocabSync`) prevents drift between the
hardcoded fallback and the JSON.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, Optional


_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "data", "form_factor_vocab.json")
_LOGGER = logging.getLogger(__name__)

# Hardcoded fallback — kept in sync with the JSON vocab by
# `test_form_factor_vocab.py::TestVocabSync`. Order matches the JSON.
_FALLBACK_IDS = (
    "capsule",
    "softgel",
    "tablet",
    "chewable",
    "gummy",
    "powder",
    "liquid",
    "tincture",
    "lozenge",
    "sublingual",
    "drops",
    "spray",
    "bar",
    "patch",
    "topical",
    "tea_bag",
    "other",
    "unknown",
)

FORM_FACTOR_UNKNOWN = "unknown"


def _normalize_text(value: Any) -> str:
    """Lowercase, strip, collapse whitespace + punctuation to single spaces."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[._/\\,;:|()\[\]{}]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@lru_cache(maxsize=1)
def _load_vocab() -> Dict[str, Any]:
    """Load the vocab JSON. Returns a dict with `entries` (list) and
    `alias_index` / `langual_index` (dicts) precomputed for fast lookup.
    Falls back to the hardcoded list if the JSON is missing or invalid.
    """
    try:
        with open(_VOCAB_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("form_factors", [])
        if not isinstance(entries, list) or not entries:
            raise ValueError("form_factors array empty or malformed")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        _LOGGER.warning(
            "form_factor_vocab.json unavailable (%s); using hardcoded fallback", exc
        )
        entries = [{"id": fid, "aliases": [fid.replace("_", " ")], "dsld_langual_codes": []} for fid in _FALLBACK_IDS]

    alias_index: Dict[str, str] = {}
    langual_index: Dict[str, str] = {}
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
        for code in entry.get("dsld_langual_codes", []) or []:
            norm_code = str(code or "").strip().lower()
            if norm_code:
                langual_index.setdefault(norm_code, fid)

    return {
        "entries": entries,
        "alias_index": alias_index,
        "langual_index": langual_index,
    }


def _canonical_ids() -> frozenset[str]:
    return frozenset(
        str(e.get("id") or "").strip().lower()
        for e in _load_vocab()["entries"]
        if isinstance(e, dict) and e.get("id")
    )


# Public attribute — recomputed on every access so test-time vocab edits
# pick up after `_load_vocab.cache_clear()`.
def __getattr__(name: str):
    if name == "FORM_FACTOR_IDS":
        return _canonical_ids()
    raise AttributeError(name)


def canonicalize_form_factor(
    value: Any,
    *,
    langual_code: Optional[str] = None,
) -> str:
    """Map a raw form-factor signal to one of the canonical vocab IDs.

    Matching order (most specific first):
      1. DSLD `langualCodeDescription` lookup (when `langual_code` is
         supplied) — most authoritative when the raw DSLD payload is
         available, because the code is a stable identifier.
      2. Exact alias match against the normalized free-text value.
      3. Substring alias match (e.g. "Softgel Capsule" -> `softgel` even
         when the alias list happens not to include that exact phrasing).
      4. Fall back to `FORM_FACTOR_UNKNOWN`.

    Returns the canonical ID string. Never returns None.
    """
    vocab = _load_vocab()

    # 1. DSLD langual code — most specific.
    if langual_code:
        code = str(langual_code).strip().lower()
        if code in vocab["langual_index"]:
            return vocab["langual_index"][code]

    text = _normalize_text(value)
    if not text:
        return FORM_FACTOR_UNKNOWN

    # 2. Exact alias match.
    if text in vocab["alias_index"]:
        return vocab["alias_index"][text]

    # 3. Substring match. Longest alias first so "softgel capsule" beats
    #    "capsule".
    sorted_aliases = sorted(vocab["alias_index"].keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        if alias in text:
            return vocab["alias_index"][alias]

    return FORM_FACTOR_UNKNOWN
