"""SB-9: grape_seed v6 contract annotation + cognigrape typo fix.

The v6 audit reported standardized_botanicals.grape_seed as 5 aliases
→ 5 UNIIs. Inspection shows:

  - 6TG3V35HTV  'vitis vinifera' (species — Vitis vinifera generic)
  - RDS2V6DVY5  'grape seed extract' (entry's own UNII — preparation
                spec)
  - ZZE3L9H7KH  'grape seed proanthocyanidins' (marker-compound UNII)
  - 930MLC8XGG  'grapeseed' (variant registry term)
  - 7G50Y5P93W  "masquelier's OPC" (branded OPC product UNII —
                Masquelier's Anthogenol, the original OPC extract that
                later became Pycnogenol)

This is the same-species/marker-compound/preparation-variant pattern
established in SB-4 (boswellia branded), SB-5 (bilberry), SB-6
(ginger), and SB-8 (rhodiola). Aliases describe what the entry is
standardized TO, not cross-species misplacement.

Secondary issue: ``cognigrape`` entry has a typo alias (``gognigrape``)
and empty external_ids. Cognigrape is a Bionap branded
anthocyanin-standardized red-grape extract — fix the typo and set
the UNII.

SB-9 scope

- standardized_botanicals.grape_seed (UNII RDS2V6DVY5):
    - Refine standard_name "Grape Seed" → "Grape Seed (Vitis vinifera
      seed)".
    - Add v6 contract fields:
        bonus_eligible / standardization_basis / marker_compounds
        (OPCs, proanthocyanidins, polyphenols including catechin,
        epicatechin, gallic acid) / bonus_rationale / sources.
    - Add marker-explicit aliases ("grape seed extract standardized to
      95% OPCs", "MegaNatural-BP", etc.).
    - Document the existence of a sibling ``grape_seed_extract`` entry
      claiming the same UNII RDS2V6DVY5 — flagged for future merger
      decision (out of SB-9 scope).

- standardized_botanicals.cognigrape:
    - Fix typo alias 'gognigrape' → 'cognigrape' (the original was a
      copy-paste artifact).
    - Set external_ids.unii to 'RDS2V6DVY5' (grape seed extract
      preparation UNII matches Cognigrape's chemistry per Bionap
      monograph — anthocyanin-rich grape-seed-pomace extract).

No new canonicals. botanical_ingredients.grape_seed (UNII
C34U15ICXA) continues to host plain identity (no bonus).
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


def test_grape_seed_is_bonus_eligible_with_marker_percent(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "grape_seed")
    assert e, "grape_seed entry missing"
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("proanthocyanidin" in m or "opc" in m for m in markers), (
        f"marker_compounds must include OPCs / proanthocyanidins. Got: "
        f"{e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one PMID/DOI/NIH"


def test_grape_seed_standard_name_is_species_precise(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "grape_seed")
    sn = (e.get("standard_name") or "").lower()
    assert "vitis vinifera" in sn or "grape seed" in sn, (
        f"standard_name should name 'Grape Seed' / 'Vitis vinifera'. "
        f"Got: {e.get('standard_name')!r}"
    )


def test_grape_seed_carries_marker_explicit_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "grape_seed")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("opc" in a or "proanthocyanidin" in a))
        or "% opc" in a
        or "% proanthocyanidin" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"grape_seed must carry at least one marker-explicit alias. "
        f"Got: {e.get('aliases')}"
    )


def test_grape_seed_retains_existing_identity_aliases(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "grape_seed")
    aliases = _lc(e.get("aliases", []))
    for required in ("vitis vinifera", "grape seed extract", "grapeseed"):
        assert required in aliases, (
            f"grape_seed must retain identity alias '{required}'. Got: "
            f"{e.get('aliases')}"
        )


def test_cognigrape_typo_fixed(sbot):
    """The 'gognigrape' alias is a copy-paste typo; must be replaced
    by the correct 'cognigrape' phrasing."""
    e = _find(sbot.get("standardized_botanicals", []), "cognigrape")
    assert e, "cognigrape entry missing"
    aliases = _lc(e.get("aliases", []))
    assert "gognigrape" not in aliases, (
        f"cognigrape must not retain the typo 'gognigrape' alias. Got: "
        f"{e.get('aliases')}"
    )
    assert "cognigrape" in aliases, (
        f"cognigrape must carry the canonical 'cognigrape' alias. Got: "
        f"{e.get('aliases')}"
    )


def test_cognigrape_has_unii(sbot):
    """cognigrape external_ids must be populated so the audit's
    no-target-UNII flag clears."""
    e = _find(sbot.get("standardized_botanicals", []), "cognigrape")
    unii = (e.get("external_ids") or {}).get("unii")
    assert unii, (
        f"cognigrape external_ids.unii must be populated. Got: "
        f"{e.get('external_ids')}"
    )
