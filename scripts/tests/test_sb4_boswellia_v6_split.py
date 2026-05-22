"""SB-4: Boswellia §8.5 cleanup + v6 bonus-contract annotation.

Boswellia is the worst single contamination in the v6 audit: 14
aliases mapping to 5 distinct UNIIs. The split is fundamentally
between the entry's nominal identity (Boswellia serrata, UNII
4PW41QCO2M) and the alias 'frankincense extract' (Boswellia carterii,
UNII R9XLF1R1WM — Somali frankincense, a different species).

The branded names that show different UNIIs (5-Loxin Advanced
UNII 6YG6TBW7NK; 5-Loxin D8UQ4B2T7M; Joint Shield LX0XHE5NLN;
Boswellin / Bosclear no-UNII-yet) are FDA-registered formulation
substances of B. serrata — they legitimately stay in this entry as
the bonus pathway for branded standardized extracts.

SB-4 scope (this commit)

- Add v6 contract fields to standardized_botanicals.boswellia:
    bonus_eligible / standardization_basis / marker_compounds /
    bonus_rationale / sources.
- Refine standard_name to be species-precise: "Boswellia" →
  "Boswellia serrata".
- Add marker-explicit aliases (`'boswellia serrata extract standardized
  to 65% boswellic acids'`, etc.) so labels carrying the
  standardization phrasing match directly.
- Move 'frankincense extract' (B. carterii, R9XLF1R1WM) out of
  standardized_botanicals.boswellia. Add it to a NEW
  botanical_ingredients.boswellia_carterii canonical entry (UNII
  R9XLF1R1WM) — identity only, no A5b bonus pathway.

Out of scope

- Branded forms (5-Loxin, Joint Shield, Boswellin, Bosclear) retained
  here because they are documented standardized B. serrata extracts
  with specific AKBA / boswellic-acid % marker claims. Their
  formulation UNIIs differ from the species UNII but the species
  identity is B. serrata.
- Plain identity aliases ('boswellia resin', 'indian frankincense',
  etc.) are duplicates of botanical_ingredients.boswellia_serrata_resin
  but stay here for runtime matching (per SB-2 preserve-plain-aliases
  policy on bonus-eligible entries — the enricher's meets_threshold
  gate filters non-standardized labels).
"""
from __future__ import annotations

import json
import os
import sys
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


def test_boswellia_is_bonus_eligible_with_marker_percent(sbot):
    """Boswellia (B. serrata, UNII 4PW41QCO2M) is bonus-eligible: the
    entry's standardization marker is boswellic acids (typically 65%)
    with AKBA as a sub-marker (often 5-30% in branded extracts)."""
    e = _find(sbot.get("standardized_botanicals", []), "boswellia")
    assert e is not None, "boswellia entry missing"
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("boswellic" in m for m in markers), (
        f"marker_compounds must name boswellic acids. Got: {e.get('marker_compounds')}"
    )
    assert any("akba" in m or "acetyl" in m for m in markers), (
        f"marker_compounds must name AKBA (3-acetyl-11-keto-beta-boswellic acid). "
        f"Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, (
        "sources[] must cite at least one PMID/DOI/NIH-ODS/ABC URL"
    )


def test_boswellia_standard_name_is_species_precise(sbot):
    """standard_name must be 'Boswellia serrata', not just 'Boswellia'.
    The entry's UNII (4PW41QCO2M) names this exact species; the
    bonus-eligibility contract benefits from naming the species in
    line with the UNII."""
    e = _find(sbot.get("standardized_botanicals", []), "boswellia")
    assert (e.get("standard_name") or "").lower() == "boswellia serrata", (
        f"standard_name must be 'Boswellia serrata'. Got: "
        f"{e.get('standard_name')!r}"
    )


def test_boswellia_carries_marker_explicit_aliases(sbot):
    """At least one alias must include the standardization phrasing
    so labels carrying explicit boswellic-acid % match directly."""
    e = _find(sbot.get("standardized_botanicals", []), "boswellia")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and "boswellic" in a)
        or "% boswellic" in a
        or "% akba" in a
        or "akba standardized" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"boswellia must carry at least one marker-explicit alias. Got: "
        f"{e.get('aliases')}"
    )


def test_boswellia_no_longer_aliases_carterii_frankincense(sbot):
    """'frankincense extract' resolves to UNII R9XLF1R1WM (B. carterii),
    a different species from this entry's UNII 4PW41QCO2M (B. serrata).
    §8.5 misplacement — must move to a separate canonical."""
    e = _find(sbot.get("standardized_botanicals", []), "boswellia")
    aliases = _lc(e.get("aliases", []))
    assert "frankincense extract" not in aliases, (
        f"§8.5: 'frankincense extract' is B. carterii (UNII R9XLF1R1WM), "
        f"different species from this entry. Got: {e.get('aliases')}"
    )


def test_boswellia_carterii_botanical_entry_exists(botanicals):
    """New botanical_ingredients.boswellia_carterii canonical (UNII
    R9XLF1R1WM = B. carterii, Somali frankincense) — identity only, no
    A5b bonus."""
    e = _find(botanicals.get("botanical_ingredients", []), "boswellia_carterii")
    assert e, "botanical_ingredients.boswellia_carterii missing"
    assert (e.get("external_ids") or {}).get("unii") == "R9XLF1R1WM"
    aliases = _lc(e.get("aliases", []))
    for required in ("frankincense extract", "boswellia carterii"):
        assert required in aliases, (
            f"boswellia_carterii must alias '{required}'. Got: "
            f"{e.get('aliases')}"
        )


def test_boswellia_retains_branded_aliases(sbot):
    """Branded standardized extracts (5-Loxin, Joint Shield, Boswellin,
    Bosclear) stay in standardized_botanicals.boswellia — they are
    formulations of B. serrata with documented AKBA / boswellic-acid
    % marker claims, qualifying for the bonus pathway."""
    e = _find(sbot.get("standardized_botanicals", []), "boswellia")
    aliases = _lc(e.get("aliases", []))
    for branded in ("5-loxin", "boswellin", "bosclear"):
        # at least one alias mentions the brand name
        assert any(branded in a for a in aliases), (
            f"boswellia must retain branded alias mentioning '{branded}'. "
            f"Got: {e.get('aliases')}"
        )
