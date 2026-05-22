"""SB-12: sea_buckthorn fruit-oil vs seed-oil split.

The v6 audit reported standardized_botanicals.sea_buckthorn as
ambiguous — its aliases conflated fruit oil and seed oil, but the
markers documented (omega-7 / palmitoleic acid) are fruit-oil
specific. Seed oil has materially different chemistry (omega-3
α-linolenic acid + omega-6 linoleic acid, NOT palmitoleic acid),
which means a bare "seabuckthorn oil" mention would silently inherit
the wrong marker rationale.

UNII-cache verification (scripts/data/fda_unii_cache.json) confirmed
distinct UNIIs for the two oil preparations:

  - TA4JCF9S1J  HIPPOPHAE RHAMNOIDES FRUIT OIL
                (pulp/mesocarp oil; palmitoleic acid + carotenoids
                + vitamin E)
  - T53SBG6741  HIPPOPHAE RHAMNOIDES SEED OIL
                (α-linolenic acid + linoleic acid + γ-tocopherol)
  - YAA7TG74X6  HIPPOPHAE RHAMNOIDES WHOLE (species canonical;
                hosts plain identity in botanical_ingredients.json)
  - AVL0R9111T  HIPPOPHAE RHAMNOIDES FRUIT (the fruit/berry, not
                its extracted oil)

SB-12 scope

- Refine existing standardized_botanicals.sea_buckthorn → FRUIT OIL
  only:
    - standard_name "Sea Buckthorn" → "Sea Buckthorn Fruit Oil
      (Hippophae rhamnoides fruit oil)"
    - external_ids.unii = 'TA4JCF9S1J' (FRUIT OIL)
    - Drop part-ambiguous aliases ('sea buckthorn oil',
      'seabuckthorn oil', 'sea buckthorn extract', 'seaberry') —
      they could refer to seed oil or unspecified prep and must not
      silently inherit fruit-oil bonus rationale
    - Add v6 contract:
        bonus_eligible / standardization_basis=marker_percent /
        marker_compounds=[palmitoleic acid (omega-7), oleic acid
        (omega-9), carotenoids, vitamin E (tocopherols/tocotrienols)]
    - Add marker-explicit aliases (e.g.
      "sea buckthorn fruit oil standardized to omega-7
      palmitoleic acid")

- New standardized_botanicals.sea_buckthorn_seed_oil entry:
    - external_ids.unii = 'T53SBG6741' (SEED OIL)
    - markers: α-linolenic acid (omega-3), linoleic acid (omega-6),
      γ-tocopherol, plant sterols
    - v6 marker_percent contract
    - aliases: 'sea buckthorn seed oil', 'seabuckthorn seed oil',
      'hippophae rhamnoides seed oil', plus marker-explicit variants

Out of scope

- Existing botanical_ingredients.sea_buckthorn (juice powder, plain
  identity) continues to host non-oil mentions and ambiguous
  "sea buckthorn oil" plain-identity routing.
- Other Hippophae species (H. salicifolia, H. tibetana, etc.) — no
  product surface in current data; defer.
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


def test_sea_buckthorn_is_fruit_oil_precise(sbot):
    """sea_buckthorn must be refined to FRUIT OIL specifically —
    the documented markers (palmitoleic acid / omega-7) are fruit-
    oil-specific; conflating with seed oil contaminates the bonus
    rationale."""
    e = _find(sbot.get("standardized_botanicals", []), "sea_buckthorn")
    assert e, "sea_buckthorn entry missing"
    sn = (e.get("standard_name") or "").lower()
    assert "fruit oil" in sn, (
        f"standard_name must name 'fruit oil' to disambiguate from "
        f"seed oil. Got: {e.get('standard_name')!r}"
    )
    assert (e.get("external_ids") or {}).get("unii") == "TA4JCF9S1J", (
        f"external_ids.unii must be 'TA4JCF9S1J' (HIPPOPHAE RHAMNOIDES "
        f"FRUIT OIL). Got: {e.get('external_ids')}"
    )


def test_sea_buckthorn_drops_part_ambiguous_aliases(sbot):
    """Part-ambiguous aliases must NOT live on the fruit-oil entry —
    they could legitimately refer to seed oil and would silently
    inherit the wrong marker rationale."""
    e = _find(sbot.get("standardized_botanicals", []), "sea_buckthorn")
    aliases = _lc(e.get("aliases", []))
    for forbidden in ("sea buckthorn oil", "seabuckthorn oil", "sea buckthorn extract", "seaberry"):
        assert forbidden not in aliases, (
            f"§8.5: '{forbidden}' is part-ambiguous and must not "
            f"alias the fruit-oil-specific entry. Got: {e.get('aliases')}"
        )


def test_sea_buckthorn_v6_contract_fields(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "sea_buckthorn")
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("palmitoleic" in m or "omega-7" in m for m in markers), (
        f"fruit-oil marker_compounds must include palmitoleic acid / "
        f"omega-7 (the signature fruit-oil bioactive). Got: "
        f"{e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one"


def test_sea_buckthorn_carries_fruit_oil_marker_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "sea_buckthorn")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("palmitoleic" in a or "omega-7" in a))
        or "% palmitoleic" in a
        or "% omega-7" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"sea_buckthorn (fruit oil) must carry at least one marker-"
        f"explicit alias. Got: {e.get('aliases')}"
    )


def test_sea_buckthorn_seed_oil_entry_exists(sbot):
    """Companion canonical for seed oil (UNII T53SBG6741) — different
    fatty-acid profile (α-linolenic, linoleic, γ-tocopherol)."""
    e = _find(sbot.get("standardized_botanicals", []), "sea_buckthorn_seed_oil")
    assert e, "standardized_botanicals.sea_buckthorn_seed_oil missing"
    assert (e.get("external_ids") or {}).get("unii") == "T53SBG6741", (
        f"sea_buckthorn_seed_oil external_ids.unii must be "
        f"'T53SBG6741' (HIPPOPHAE RHAMNOIDES SEED OIL). Got: "
        f"{e.get('external_ids')}"
    )
    aliases = _lc(e.get("aliases", []))
    for required in ("sea buckthorn seed oil", "hippophae rhamnoides seed oil"):
        assert required in aliases, (
            f"sea_buckthorn_seed_oil must alias '{required}'. Got: "
            f"{e.get('aliases')}"
        )
    assert e.get("bonus_eligible") is True
    markers = _lc(e.get("marker_compounds") or [])
    assert any(
        "linolenic" in m or "linoleic" in m or "tocopherol" in m
        for m in markers
    ), (
        f"sea_buckthorn_seed_oil marker_compounds must name seed-oil "
        f"signature fatty acids (α-linolenic / linoleic / "
        f"γ-tocopherol). Got: {e.get('marker_compounds')}"
    )


def test_sea_buckthorn_seed_oil_carries_marker_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "sea_buckthorn_seed_oil")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("linolenic" in a or "linoleic" in a or "tocopherol" in a))
        or "% linolenic" in a
        or "% linoleic" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"sea_buckthorn_seed_oil must carry at least one marker-"
        f"explicit alias. Got: {e.get('aliases')}"
    )
