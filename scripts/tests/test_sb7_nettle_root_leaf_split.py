"""SB-7: nettle root vs leaf split + v6 contract annotation.

Codex's audit flagged nettle as 4 aliases → 4 UNIIs. The split is
clinically meaningful: nettle root (Urtica dioica radix, UNII
J8HE8A6E5T) and nettle leaf (Urtica dioica folium, UNII 232L6DS3Y4
under the botanical entry / X6M0DRN46Q at the extract registry
level) are different plant parts with different standardization
markers and different clinical uses:

  - Nettle ROOT: beta-sitosterol, scopoletin, lignans — used for BPH /
    benign prostatic hyperplasia.
  - Nettle LEAF: silica, formic acid, chlorophyll, polyphenols — used
    for allergy / joint support.

The current standardized_botanicals.nettle entry mixes both root- and
leaf-specific aliases ('nettle root extract', 'nettle leaf extract')
under one species UNII, and its markers field jams all three
('silica', 'beta-sitosterol', 'scopoletin') together. That's editorial
contamination — a single bonus-eligible entry should declare a
coherent standardization basis.

SB-7 scope

- Refine standardized_botanicals.nettle to be species-level only:
    standard_name: "Nettle" → "Nettle (Urtica dioica)".
    Remove plant-part aliases ('nettle root extract', 'nettle leaf
    extract') — they belong in the existing botanical_ingredients.
    nettle_root and botanical_ingredients.nettle_leaf canonicals.
    Keep species-level aliases ('urtica dioica', 'stinging nettle').
- Add v6 contract fields acknowledging dual-marker pathway: the entry
  is bonus-eligible when EITHER root markers (beta-sitosterol /
  scopoletin / lignans) OR leaf markers (silica) are declared on the
  label.
- Add marker-explicit aliases for both pathways.

Note: this is a NARROW cleanup. The existing botanical_ingredients
canonicals already correctly own part-specific aliases — products with
'nettle root extract' on the label will continue to match via the
botanical_ingredients.nettle_root entry (identity-only, no bonus).
Products with a label declaring '1% beta-sitosterol' or similar
marker % will match standardized_botanicals.nettle and trigger the
enricher's meets_threshold gate.
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


@pytest.fixture(scope="module")
def botanicals() -> Dict[str, Any]:
    with open(os.path.join(_SCRIPTS, "data", "botanical_ingredients.json")) as f:
        return json.load(f)


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def test_nettle_is_bonus_eligible_with_marker_percent(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "nettle")
    assert e, "nettle entry missing"
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    # Both root and leaf markers must be acknowledged
    assert any("sitosterol" in m or "scopoletin" in m for m in markers), (
        f"marker_compounds must include root markers (beta-sitosterol "
        f"and/or scopoletin). Got: {e.get('marker_compounds')}"
    )
    assert any("silica" in m for m in markers), (
        f"marker_compounds must include leaf marker (silica). Got: "
        f"{e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one PMID/DOI/NIH"


def test_nettle_standard_name_is_species_precise(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "nettle")
    sn = (e.get("standard_name") or "").lower()
    assert "urtica dioica" in sn or "nettle" in sn, (
        f"standard_name should include Nettle or Urtica dioica. Got: "
        f"{e.get('standard_name')!r}"
    )


def test_nettle_no_longer_aliases_plant_parts(sbot):
    """Part-specific aliases ('nettle root extract', 'nettle leaf
    extract') must move out of the species-level entry — they live in
    botanical_ingredients.nettle_root and botanical_ingredients.
    nettle_leaf respectively."""
    e = _find(sbot.get("standardized_botanicals", []), "nettle")
    aliases = _lc(e.get("aliases", []))
    for forbidden in ("nettle root extract", "nettle leaf extract"):
        assert forbidden not in aliases, (
            f"§8.5: '{forbidden}' must NOT live on standardized_botanicals."
            f"nettle (species-level entry). Got: {e.get('aliases')}"
        )


def test_nettle_retains_species_level_aliases(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "nettle")
    aliases = _lc(e.get("aliases", []))
    for required in ("urtica dioica", "stinging nettle"):
        assert required in aliases, (
            f"nettle must retain species-level alias '{required}'. Got: "
            f"{e.get('aliases')}"
        )


def test_nettle_carries_marker_explicit_aliases_for_both_parts(sbot):
    """The bonus pathway accepts EITHER root or leaf markers. Both
    pathways need at least one marker-explicit alias for direct
    matching."""
    e = _find(sbot.get("standardized_botanicals", []), "nettle")
    aliases = _lc(e.get("aliases", []))
    root_marker = any(
        ("standardized" in a and ("sitosterol" in a or "scopoletin" in a))
        or "% beta-sitosterol" in a
        for a in aliases
    )
    leaf_marker = any(
        ("standardized" in a and "silica" in a) or "% silica" in a
        for a in aliases
    )
    assert root_marker, (
        f"nettle must carry at least one root-marker alias (beta-sitosterol "
        f"or scopoletin %). Got: {e.get('aliases')}"
    )
    assert leaf_marker, (
        f"nettle must carry at least one leaf-marker alias (silica %). "
        f"Got: {e.get('aliases')}"
    )


def test_botanical_nettle_root_and_leaf_unchanged(botanicals):
    """The existing botanical_ingredients.nettle_root and
    botanical_ingredients.nettle_leaf canonicals continue to own
    part-specific identity (this test confirms they exist; SB-7
    doesn't modify them)."""
    root = _find(botanicals.get("botanical_ingredients", []), "nettle_root")
    leaf = _find(botanicals.get("botanical_ingredients", []), "nettle_leaf")
    assert root, "nettle_root botanical entry missing"
    assert leaf, "nettle_leaf botanical entry missing"
    assert (root.get("external_ids") or {}).get("unii") == "J8HE8A6E5T"
    assert (leaf.get("external_ids") or {}).get("unii") == "232L6DS3Y4"
