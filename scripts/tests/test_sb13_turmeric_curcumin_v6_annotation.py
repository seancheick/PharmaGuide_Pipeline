"""SB-13: turmeric & curcumin v6 contract annotation.

standardized_botanicals has two complementary entries for the
Curcuma longa / curcumin pathway:

  - id=curcumin   UNII IT942ZTH98 (CURCUMIN — the marker compound)
  - id=turmeric   UNII 856YO1Z64F (CURCUMA LONGA (TURMERIC) ROOT —
                  the whole rhizome)

Both UNIIs are already populated and verified via FDA UNII cache.
Both entries pre-existed with min_threshold=95 (curcuminoid %) and
list the same four curcuminoid markers (curcumin,
demethoxycurcumin, bisdemethoxycurcumin, curcuminoids). What is
missing is the v6 bonus-eligibility contract — bonus_eligible,
standardization_basis, marker_compounds, bonus_rationale, sources.

The turmeric entry's plain aliases (turmeric powder, turmeric root,
haldi) appear safe under the meets_threshold gate
(score_supplements.py:1148): raw rhizome contains only 2-5%
curcuminoids and will not satisfy the 95% percent-detection
threshold at runtime; plain identity routes to the botanical
identity entries (botanical_ingredients.turmeric and
botanical_ingredients.turmeric_root_powder).

SB-13 scope

- standardized_botanicals.curcumin: add v6 contract
    (basis=marker_percent, marker_compounds curcuminoid family,
    rationale citing 95% curcuminoid standardization and
    branded-extract families, sources).
    Add marker-explicit aliases (C3 Complex, BCM-95, Meriva).
- standardized_botanicals.turmeric: add v6 contract
    (basis=marker_percent on extract products with quantified
    curcuminoid percentage; gate enforces percentage-detection
    at runtime).
    Add marker-explicit standardization aliases.

Out of scope

- BCM-95 / C3 / Meriva potential relocation from
  botanical_ingredients to standardized_botanicals — defer.
- New entries for other Curcuma species (C. zedoaria, C.
  aromatica, etc.) — defer until product surface appears.
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


def test_curcumin_retains_marker_unii(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "curcumin")
    assert e, "curcumin entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "IT942ZTH98", (
        f"curcumin external_ids.unii must be 'IT942ZTH98' (CURCUMIN — "
        f"the marker compound, verified via FDA UNII cache). "
        f"Got: {e.get('external_ids')}"
    )


def test_curcumin_v6_contract_fields(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "curcumin")
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("curcuminoid" in m or "curcumin" in m for m in markers), (
        f"marker_compounds must include curcuminoids/curcumin. Got: "
        f"{e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one PMID/NIH"


def test_curcumin_carries_marker_explicit_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "curcumin")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and "curcuminoid" in a)
        or "% curcuminoid" in a
        or "95% curcuminoid" in a
        or "curcumin 95" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"curcumin must carry at least one marker-explicit alias "
        f"(95% curcuminoids / standardized to curcuminoids). Got: "
        f"{e.get('aliases')}"
    )


def test_turmeric_retains_rhizome_unii(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "turmeric")
    assert e, "turmeric entry missing"
    assert (e.get("external_ids") or {}).get("unii") == "856YO1Z64F", (
        f"turmeric external_ids.unii must be '856YO1Z64F' (CURCUMA "
        f"LONGA (TURMERIC) ROOT — the whole rhizome, verified via "
        f"FDA UNII cache). Got: {e.get('external_ids')}"
    )


def test_turmeric_v6_contract_fields(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "turmeric")
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "marker_percent"
    markers = _lc(e.get("marker_compounds") or [])
    assert any("curcuminoid" in m or "curcumin" in m for m in markers), (
        f"turmeric marker_compounds must include curcuminoids/curcumin "
        f"(extract standardization basis). Got: "
        f"{e.get('marker_compounds')}"
    )
    assert e.get("bonus_rationale"), "bonus_rationale must be non-empty"
    sources = e.get("sources") or []
    assert len(sources) >= 1, "sources[] must cite at least one"


def test_turmeric_carries_extract_marker_alias(sbot):
    e = _find(sbot.get("standardized_botanicals", []), "turmeric")
    aliases = _lc(e.get("aliases", []))
    marker_explicit = any(
        ("standardized" in a and ("curcuminoid" in a or "curcumin" in a))
        or "% curcuminoid" in a
        or "95% curcuminoid" in a
        for a in aliases
    )
    assert marker_explicit, (
        f"turmeric must carry at least one marker-explicit standardized-"
        f"extract alias. Got: {e.get('aliases')}"
    )
