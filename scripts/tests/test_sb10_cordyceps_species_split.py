"""SB-10: cordyceps Cordyceps sinensis vs Cordyceps militaris split.

The v6 audit flagged cordyceps as 7 aliases → 4 UNIIs. The genuine
§8.5 issue: Cordyceps sinensis (Ophiocordyceps sinensis, UNII
8Q1GYP08KU) and Cordyceps militaris (UNII J617U5X7NN) are two
biologically distinct species with different markers and clinical
profiles:

  - C. sinensis (caterpillar fungus): historically wild-harvested,
    very expensive, used in TCM. Standardization typically targets
    polysaccharides (40%+) and adenosine.
  - C. militaris: commercially cultivable, higher cordycepin content
    (3'-deoxyadenosine — the bioactive most ergogenic-supplement
    research targets). Standardization typically targets cordycepin
    (0.1%+) and beta-glucans.

Plus a 4th identity in current aliases:
  - CS-4 (UNII 821RF3P03C): Paecilomyces hepiali — a fermented strain
    historically labelled as cordyceps in TCM supplements; technically
    a different fungus.

The current entry's external_ids is EMPTY despite being bonus-eligible.

SB-10 scope

- Refine the existing standardized_botanicals.cordyceps entry to be
  species-precise to C. sinensis:
    - standard_name "Cordyceps" → "Cordyceps sinensis"
    - external_ids.unii = '8Q1GYP08KU'
    - Remove 'cordyceps militaris' alias (different species)
    - Add v6 contract fields (markers: cordycepin, adenosine,
      polysaccharides, beta-glucans)
    - Add marker-explicit aliases (40% polysaccharides, etc.)

- Create new standardized_botanicals.cordyceps_militaris entry (UNII
  J617U5X7NN):
    - For C. militaris-specific marker pathway (cordycepin %)
    - Aliases: cordyceps militaris, Cordyceps militaris, marker-
      explicit variants
    - v6 contract fields

Out of scope

- CS-4 (Paecilomyces hepiali, UNII 821RF3P03C): separate fungus —
  defer to SB-10b if products surface using CS-4 explicitly.
- Existing botanical_ingredients.cordyceps and .cordyceps_mushroom_
  powder entries continue to host plain identity.
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


def test_cordyceps_is_c_sinensis(sbot):
    """standardized_botanicals.cordyceps must be species-precise to
    Cordyceps sinensis (UNII 8Q1GYP08KU). The current empty
    external_ids and species-mixed aliases are the §8.5 root."""
    e = _find(sbot.get("standardized_botanicals", []), "cordyceps")
    assert e, "cordyceps entry missing"
    sn = (e.get("standard_name") or "").lower()
    assert "cordyceps sinensis" in sn, (
        f"standard_name must be 'Cordyceps sinensis'. Got: "
        f"{e.get('standard_name')!r}"
    )
    assert (e.get("external_ids") or {}).get("unii") == "8Q1GYP08KU", (
        f"external_ids.unii must be '8Q1GYP08KU' (Cordyceps sinensis). "
        f"Got: {e.get('external_ids')}"
    )


def test_cordyceps_no_longer_aliases_c_militaris(sbot):
    """C. militaris (UNII J617U5X7NN) is a different species —
    must move to standardized_botanicals.cordyceps_militaris."""
    e = _find(sbot.get("standardized_botanicals", []), "cordyceps")
    aliases = _lc(e.get("aliases", []))
    assert "cordyceps militaris" not in aliases, (
        f"§8.5: 'cordyceps militaris' must NOT alias the C. sinensis "
        f"entry. Got: {e.get('aliases')}"
    )


def test_cordyceps_v6_contract_fields(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "cordyceps")
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") in (
        "marker_percent", "mushroom_fraction",
    )
    markers = _lc(e.get("marker_compounds") or [])
    assert any("polysaccharide" in m or "beta-glucan" in m for m in markers), (
        f"marker_compounds must include polysaccharides/beta-glucans. "
        f"Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one"


def test_cordyceps_militaris_entry_exists(sbot):
    """New canonical for C. militaris (UNII J617U5X7NN) — different
    species with cordycepin-focused marker pathway."""
    e = _find(sbot.get("standardized_botanicals", []), "cordyceps_militaris")
    assert e, "standardized_botanicals.cordyceps_militaris missing"
    assert (e.get("external_ids") or {}).get("unii") == "J617U5X7NN"
    aliases = _lc(e.get("aliases", []))
    for required in ("cordyceps militaris", "c. militaris"):
        assert required in aliases, (
            f"cordyceps_militaris must alias '{required}'. Got: "
            f"{e.get('aliases')}"
        )
    assert e.get("bonus_eligible") is True
    markers = _lc(e.get("marker_compounds") or [])
    assert any("cordycepin" in m for m in markers), (
        f"cordyceps_militaris marker_compounds must name cordycepin "
        f"(its signature bioactive). Got: {e.get('marker_compounds')}"
    )


def test_cordyceps_sinensis_carries_marker_explicit_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "cordyceps")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("polysaccharide" in a or "beta-glucan" in a or "adenosine" in a))
        or "% polysaccharide" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"cordyceps (C. sinensis) must carry at least one marker-explicit "
        f"alias. Got: {e.get('aliases')}"
    )


def test_cordyceps_militaris_carries_cordycepin_marker_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "cordyceps_militaris")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and "cordycepin" in a) or "% cordycepin" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"cordyceps_militaris must carry at least one cordycepin-explicit "
        f"alias. Got: {e.get('aliases')}"
    )
