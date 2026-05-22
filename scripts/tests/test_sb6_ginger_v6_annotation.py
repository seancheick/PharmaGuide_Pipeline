"""SB-6: ginger_extract v6 bonus-contract annotation.

Per the v6 audit, ginger_extract had 10 aliases → 5 UNIIs. As with
SB-5 (bilberry), the multi-UNII pattern reflects marker-compound and
preparation registry entries for the SAME species (Zingiber
officinale), not cross-species §8.5 misplacement:

  - C5529G5JPQ  Zingiber officinale (entry's own species UNII)
  - V2ZD052TS1  'total gingerols and shogaols' (marker-compound UNII)
  - SAS9Z1SVUK  'standardized ginger gingerols' (marker UNII)
  - 925QK2Z900  6-gingerol (specific marker UNII)
  - UL302SFN7L  'zingiber' (generic registry term)

Marker-compound UNIIs in alias lists are acceptable for a bonus-
eligible entry — they describe what the entry is standardized TO, not
a different species identity.

SB-6 scope

- Refine standard_name "Ginger Extract" → "Ginger (Zingiber
  officinale)".
- Add v6 contract fields (bonus_eligible / standardization_basis /
  marker_compounds / bonus_rationale / sources).
- Add marker-explicit aliases for direct matching of labels with
  standardization claims (5% / 20% gingerols, GingerForce brand,
  etc.).

No new canonicals. botanical_ingredients already has ginger_extract,
ginger_root entries that handle plain identity.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPTS = os.path.join(_ROOT, "scripts")


@pytest.fixture(scope="module")
def sbot() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "standardized_botanicals.json")) as f:
        return json.load(f)


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def test_ginger_extract_is_bonus_eligible_with_marker_percent(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "ginger_extract")
    assert e, "ginger_extract entry missing"
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("gingerol" in m for m in markers), (
        f"marker_compounds must name gingerols. Got: {e.get('marker_compounds')}"
    )
    assert any("shogaol" in m for m in markers), (
        f"marker_compounds should also name shogaols (second marker). "
        f"Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one PMID/DOI/NIH"


def test_ginger_standard_name_is_species_precise(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "ginger_extract")
    sn = (e.get("standard_name") or "").lower()
    assert "zingiber officinale" in sn or "ginger" in sn, (
        f"standard_name should include Ginger or Zingiber officinale. "
        f"Got: {e.get('standard_name')!r}"
    )


def test_ginger_carries_marker_explicit_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "ginger_extract")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("gingerol" in a or "shogaol" in a))
        or "% gingerol" in a
        or "% shogaol" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"ginger_extract must carry at least one marker-explicit alias. "
        f"Got: {e.get('aliases')}"
    )


def test_ginger_retains_existing_identity_aliases(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "ginger_extract")
    aliases = _lc(e.get("aliases", []))
    for required in (
        "zingiber officinale",
        "ginger root extract",
        "ginger extract",
        "ginger rhizome",
    ):
        assert required in aliases, (
            f"ginger_extract must retain identity alias '{required}'. "
            f"Got: {e.get('aliases')}"
        )
