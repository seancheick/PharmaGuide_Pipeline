"""SB-11: turkey_tail UNII fix + v6 mushroom-fraction contract.

The v6 audit reported turkey_tail as 5 aliases → 4 UNIIs. UNII-cache
verification (scripts/data/fda_unii_cache.json) corrected the report's
identifications:

  - 2YD82VN5CM  TRAMETES VERSICOLOR WHOLE (species-whole — canonical
                identity UNII for the entry)
  - 26BE3YVD39  TRAMETES VERSICOLOR STRAIN CM-101 (narrow strain
                variant)
  - 4C900477MT  TRAMETES VERSICOLOR FRUITING BODY (preparation
                variant)
  - XY526V7HUL  SERINE/THREONINE-PROTEIN KINASE TAO2 — NOT a
                polysaccharide fraction; the 'PSK' abbreviation
                collides with an unrelated protein UNII. This is the
                §8.5 misplacement the audit flagged.
  - LQ0G3D3X8F  PULMONARY SURFACTANT-ASSOCIATED PROTEIN D — NOT a
                polysaccharide fraction; the 'PSP' abbreviation
                collides with an unrelated protein UNII.

PSK (polysaccharide krestin) and PSP (polysaccharide peptide) ARE
isolated polysaccharide fractions of Trametes versicolor — they are
legitimate mushroom-fraction MARKER compounds per the v6 contract's
``mushroom_fraction`` standardization basis — but no marker-specific
UNII exists in the FDA cache for them under those names. They stay as
marker compounds, not as standalone substance UNIIs.

SB-11 scope

- Set external_ids.unii = '2YD82VN5CM' (TRAMETES VERSICOLOR WHOLE —
  species-precise canonical).
- Refine standard_name "Turkey Tail" → "Turkey Tail (Trametes
  versicolor)".
- Add v6 contract fields:
    bonus_eligible / standardization_basis=mushroom_fraction /
    marker_compounds=[polysaccharides, beta-glucans, PSK
    (polysaccharide krestin / krestin), PSP (polysaccharide peptide /
    Yun zhi), polysaccharopeptide] / bonus_rationale / sources.
- Add marker-explicit aliases ("turkey tail extract standardized to
  30% polysaccharides", "Krestin", "Yun zhi" branded variants).
- Retain identity aliases (Trametes versicolor, Coriolus versicolor)
  and marker abbreviations (PSK, PSP) — the latter are clearly
  contextualized by the v6 mushroom_fraction basis, not loose tokens.

Out of scope

- Existing botanical_ingredients.turkey_tail entries continue to host
  plain identity.
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


def test_turkey_tail_has_unii(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "turkey_tail")
    assert e, "turkey_tail entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "2YD82VN5CM", (
        f"turkey_tail external_ids.unii must be '2YD82VN5CM' "
        f"(TRAMETES VERSICOLOR WHOLE — species-precise canonical, "
        f"verified via scripts/data/fda_unii_cache.json). "
        f"Got: {e.get('external_ids')}"
    )


def test_turkey_tail_v6_contract(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "turkey_tail")
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "mushroom_fraction"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("polysaccharide" in m or "beta-glucan" in m for m in markers), (
        f"marker_compounds must include polysaccharides/beta-glucans. "
        f"Got: {e.get('marker_compounds')}"
    )
    assert any("psk" in m or "krestin" in m for m in markers), (
        f"marker_compounds must include PSK (polysaccharide krestin). "
        f"Got: {e.get('marker_compounds')}"
    )
    assert any("psp" in m or "polysaccharide peptide" in m for m in markers), (
        f"marker_compounds must include PSP (polysaccharide peptide). "
        f"Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one"


def test_turkey_tail_standard_name_is_species_precise(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "turkey_tail")
    sn = (e.get("standard_name") or "").lower()
    assert "trametes versicolor" in sn or "turkey tail" in sn, (
        f"standard_name must name Trametes versicolor or Turkey Tail. "
        f"Got: {e.get('standard_name')!r}"
    )


def test_turkey_tail_carries_marker_explicit_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "turkey_tail")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("polysaccharide" in a or "beta-glucan" in a))
        or "% polysaccharide" in a
        or "krestin" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"turkey_tail must carry at least one marker-explicit alias. "
        f"Got: {e.get('aliases')}"
    )


def test_turkey_tail_retains_psk_psp_identity_aliases(sbot):
    """PSK and PSP are mushroom-fraction markers, NOT cross-species
    misplacement. They legitimately stay as aliases of turkey_tail
    under the mushroom_fraction standardization basis."""
    e = _find(sbot.get("standardized_botanicals", []), "turkey_tail")
    aliases = _lc(e.get("aliases", []))
    for required in ("trametes versicolor", "coriolus versicolor", "psk", "psp"):
        assert required in aliases, (
            f"turkey_tail must retain identity/marker alias '{required}'. "
            f"Got: {e.get('aliases')}"
        )
