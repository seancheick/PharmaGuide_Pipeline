"""B2: branded inactive entries.

7 new branded-inactive entries in other_ingredients.json plus alias
additions to existing entries to route May 22 unmapped-inactive
occurrences to clean identity homes.

New entries:
  OI_ULTRA_TEX_4                          Ingredion modified food starch
  OI_FLORIDA_CRYSTALS                     organic cane sugar (ASR Group)
  OI_PANMOL_B_COMPLEX                     yeast-fermented B-vitamin complex
  OI_ALOE_POLYMAX                         branded aloe vera concentrate
  OI_PUREALGAE_OMEGA3                     algal omega-3 (Nature Made/Pharmavite)
  OI_PUREPLANT_OMEGA3                     plant-source omega-3
  OI_CONCENTRATED_SEAWATER_MINERAL_COMPLEX  multimineral seawater

Alias additions:
  OI_ULTRA_PURE_MARINE_OIL  + 'Highly Refined Marine Oil Concentrate'
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def other_doc() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "other_ingredients.json")) as f:
        return json.load(f)


B2_NEW_IDS = [
    "OI_ULTRA_TEX_4",
    "OI_FLORIDA_CRYSTALS",
    "OI_PANMOL_B_COMPLEX",
    "OI_ALOE_POLYMAX",
    "OI_PUREALGAE_OMEGA3",
    "OI_PUREPLANT_OMEGA3",
    "OI_CONCENTRATED_SEAWATER_MINERAL_COMPLEX",
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("eid", B2_NEW_IDS)
def test_new_entry_present(other_doc, eid):
    e = _find(other_doc.get("other_ingredients", []), eid)
    assert e, f"{eid} missing from other_ingredients.json"
    assert e.get("standard_name")
    assert e.get("aliases"), f"{eid} must have aliases"
    assert e.get("last_updated") == "2026-05-22"


def test_ultra_tex_4_aliases(other_doc):
    e = _find(other_doc.get("other_ingredients", []), "OI_ULTRA_TEX_4")
    aliases = _lc(e.get("aliases", []))
    assert "ultra-tex 4" in aliases


def test_florida_crystals_aliases(other_doc):
    e = _find(other_doc.get("other_ingredients", []), "OI_FLORIDA_CRYSTALS")
    aliases = _lc(e.get("aliases", []))
    assert "florida crystals" in aliases


def test_aloe_polymax_aliases(other_doc):
    e = _find(other_doc.get("other_ingredients", []), "OI_ALOE_POLYMAX")
    aliases = _lc(e.get("aliases", []))
    # Both surfaced unmapped variants must be covered
    assert "aloe polymax" in aliases
    assert "aloe polymax+" in aliases
    assert "organic aloe polymax" in aliases


def test_pureplant_pureplant_omega3(other_doc):
    """The 'Pure*Omega3' family — both algae and plant variants must
    be present so the May 22 unmapped surface routes."""
    a = _find(other_doc.get("other_ingredients", []), "OI_PUREALGAE_OMEGA3")
    p = _find(other_doc.get("other_ingredients", []), "OI_PUREPLANT_OMEGA3")
    a_aliases = _lc(a.get("aliases", []))
    p_aliases = _lc(p.get("aliases", []))
    assert "purealgaeomega3 oil" in a_aliases
    assert "pureplantomega3 oil" in p_aliases


def test_marine_oil_concentrate_alias_added(other_doc):
    """The 'Highly Refined Marine Oil Concentrate' label phrase
    must alias to the existing OI_ULTRA_PURE_MARINE_OIL entry."""
    e = _find(other_doc.get("other_ingredients", []), "OI_ULTRA_PURE_MARINE_OIL")
    aliases = _lc(e.get("aliases", []))
    assert "highly refined marine oil concentrate" in aliases


def test_metadata_invariant(other_doc):
    declared = other_doc["_metadata"]["total_entries"]
    actual = len(other_doc["other_ingredients"])
    assert declared == actual, f"declared={declared}, actual={actual}"
