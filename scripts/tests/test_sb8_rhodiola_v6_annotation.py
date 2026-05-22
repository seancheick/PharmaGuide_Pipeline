"""SB-8: rhodiola UNII fix + v6 bonus-contract annotation.

The audit reported standardized_botanicals.rhodiola as 7 aliases → 5
UNIIs. Plus: the entry's external_ids.unii is EMPTY — no canonical
UNII assigned. The aliases break down as:

  - 3S5ITS5ULN  Rhodiola rosea (entry's intended species; 3 aliases)
  - 7FPZ0AY7TI  'golden root' (registry term variant)
  - P7T00DK30P  'rose root' (registry term variant)
  - RH0WP583U3  'roseroot' (registry term variant)
  - 11R149C3CY  'rhodiola root' (registry — R. quadrifida / R. sacra!)

The first four are R. rosea identity (same-species preparation registry
pattern from SB-5/SB-6). The fifth is a generic 'rhodiola root' that
the UNII registry assigns to R. quadrifida / R. sacra rather than
R. rosea — a §8.5 risk because supplement-context labels saying
'rhodiola root' typically mean R. rosea.

SB-8 scope

- Set external_ids.unii = '3S5ITS5ULN' (Rhodiola rosea) — close the
  missing-UNII gap on a bonus-eligible entry.
- Refine standard_name "Rhodiola" → "Rhodiola rosea".
- Add v6 contract fields:
    bonus_eligible / standardization_basis / marker_compounds
    (rosavins, salidroside, rosin, rosarin) / bonus_rationale
    (cites the standard 3% rosavins + 1% salidroside SHR-5 spec) /
    sources.
- Add marker-explicit aliases ("rhodiola rosea extract standardized
  to 3% rosavins, 1% salidroside", "SHR-5", branded extracts).
- Keep 'rhodiola root' alias for runtime matching (supplement-context
  convention is R. rosea) BUT document the UNII-registry ambiguity
  in notes so future audits know this is an editorial decision, not
  a true identity match.
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


def test_rhodiola_has_rosea_unii(sbot):
    """standardized_botanicals.rhodiola external_ids.unii must be
    populated with R. rosea's UNII 3S5ITS5ULN — closing the
    missing-target-UNII gap on a bonus-eligible entry."""
    e = _find(sbot.get("standardized_botanicals", []), "rhodiola")
    assert e, "rhodiola entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "3S5ITS5ULN", (
        f"rhodiola external_ids.unii must be '3S5ITS5ULN' (Rhodiola rosea). "
        f"Got: {e.get('external_ids')}"
    )


def test_rhodiola_is_bonus_eligible_with_marker_percent(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "rhodiola")
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("rosavin" in m for m in markers), (
        f"marker_compounds must name rosavins. Got: {e.get('marker_compounds')}"
    )
    assert any("salidroside" in m for m in markers), (
        f"marker_compounds must name salidroside. Got: {e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one PMID/DOI/NIH"


def test_rhodiola_standard_name_is_species_precise(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "rhodiola")
    sn = (e.get("standard_name") or "").lower()
    assert "rhodiola rosea" in sn, (
        f"standard_name must include 'Rhodiola rosea' for species "
        f"precision (the bonus pathway is R. rosea-specific; other "
        f"Rhodiola species have different marker profiles). Got: "
        f"{e.get('standard_name')!r}"
    )


def test_rhodiola_carries_marker_explicit_aliases(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "rhodiola")
    aliases = _lc(e.get("aliases", []))
    rosavin_explicit = any(
        ("standardized" in a and "rosavin" in a) or "% rosavin" in a
        for a in aliases
    )
    salidroside_explicit = any(
        ("standardized" in a and "salidroside" in a) or "% salidroside" in a
        for a in aliases
    )
    assert rosavin_explicit, (
        f"rhodiola must carry at least one rosavins-explicit alias. "
        f"Got: {e.get('aliases')}"
    )
    assert salidroside_explicit, (
        f"rhodiola must carry at least one salidroside-explicit alias. "
        f"Got: {e.get('aliases')}"
    )


def test_rhodiola_retains_existing_identity_aliases(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "rhodiola")
    aliases = _lc(e.get("aliases", []))
    for required in (
        "rhodiola rosea",
        "golden root",
        "arctic root",
        "rhodiola rosea extract",
    ):
        assert required in aliases, (
            f"rhodiola must retain identity alias '{required}'. Got: "
            f"{e.get('aliases')}"
        )
