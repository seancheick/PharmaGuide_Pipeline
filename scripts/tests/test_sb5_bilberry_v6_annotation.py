"""SB-5: bilberry v6 bonus-contract annotation.

The audit flagged standardized_botanicals.bilberry as 6 aliases → 4
UNIIs. Closer inspection shows all four UNIIs (9P2U39H18W,
R911H793SU, V9S692O326, KK0KHX972K) are FDA-registered preparation
variants of the same species (Vaccinium myrtillus) — they are not
cross-species §8.5 misplacement. The contamination is editorial
(preparation registry drift), not identity drift, and follows
Codex's "branded forms / preparation variants of the same species
legitimately stay" guidance from the SB-4 round.

SB-5 scope

- Refine standard_name to be species-precise: "Bilberry" →
  "Bilberry (Vaccinium myrtillus)".
- Add v6 contract fields:
    bonus_eligible / standardization_basis / marker_compounds /
    bonus_rationale / sources.
- Add marker-explicit aliases ("bilberry extract standardized to
  25% anthocyanosides", "Mirtoselect" branded extract, etc.) so
  labels carrying the standardization phrase match directly.
- Document the preparation-variant UNIIs in notes.

No new canonicals are created here. botanical_ingredients already has
bilberry and bilberry_fruit entries for plain identity; the
preparation-variant aliases on standardized_botanicals.bilberry stay
for runtime matching, gated at scoring time by the enricher's
meets_threshold check (per the established SB-2 preserve-plain-aliases
policy).
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


def test_bilberry_is_bonus_eligible_with_marker_percent(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "bilberry")
    assert e, "bilberry entry missing"
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("anthocyan" in m for m in markers), (
        f"marker_compounds must name anthocyanins/anthocyanosides. "
        f"Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one PMID/DOI/NIH"


def test_bilberry_standard_name_is_species_precise(sbot):
    """standard_name should make the species explicit so the bonus
    contract reads cleanly."""
    e = _find(sbot.get("standardized_botanicals", []), "bilberry")
    sn = (e.get("standard_name") or "").lower()
    assert "vaccinium myrtillus" in sn or "bilberry" in sn, (
        f"standard_name must include 'Bilberry' or species 'Vaccinium "
        f"myrtillus'. Got: {e.get('standard_name')!r}"
    )


def test_bilberry_carries_marker_explicit_alias(sbot):
    """At least one alias must carry the standardization phrasing
    (anthocyanosides %, Mirtoselect branded extract, etc.)."""
    e = _find(sbot.get("standardized_botanicals", []), "bilberry")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("anthocyan" in a))
        or "% anthocyan" in a
        or "mirtoselect" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"bilberry must carry at least one marker-explicit alias. Got: "
        f"{e.get('aliases')}"
    )


def test_bilberry_retains_v_myrtillus_identity(sbot):
    """All existing identity aliases (V. myrtillus, European blueberry,
    whortleberry, bilberry extract variants) must be preserved — they
    are preparation variants of the same species, not §8.5
    misplacement."""
    e = _find(sbot.get("standardized_botanicals", []), "bilberry")
    aliases = _lc(e.get("aliases", []))
    for required in (
        "vaccinium myrtillus",
        "european blueberry",
        "bilberry extract",
        "whortleberry",
    ):
        assert required in aliases, (
            f"bilberry must retain identity alias '{required}'. Got: "
            f"{e.get('aliases')}"
        )
