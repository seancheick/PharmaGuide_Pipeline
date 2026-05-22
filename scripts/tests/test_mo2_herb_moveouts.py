"""MO-2: second move-out batch from standardized_botanicals.

7 more plain-identity entries with no documented standardization
marker move to botanical_ingredients.json. Same pattern as MO-1.

Selection criteria (same as MO-1, applied alphabetically next):
  - Zero alias collisions with existing bot entries
  - No existing bot entry with matching latin_name/alias overlap
  - All 7 carry verified FDA UNIIs

Entries

  blue_green_algae   UNII 49VG1X560X  Aphanizomenon flos-aquae
  century_plant      UNII 024852X0VD  Agave americana
  d_mannose          UNII PHA4727WTP  Mannose (UTI sugar)
  damiana            UNII 812R0W1I3K  Turnera diffusa leaf
  elder_flower       UNII 07V4DX094T  Sambucus nigra flower
  galdieria          UNII 2E5CL9KYZ8  Galdieria sulphuraria (algae)
  grapefruit_seed    UNII 598D944HOL  Citrus paradisi seed

Out of scope

  - astaxanthin_haematococcus_pluvialis (separate std entry with
    branded aliases — deferred to PROMOTE_V6_BRANDED batch)
  - 38 remaining MOVE candidates (queued for MO-3..MO-7)
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def std_doc() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "standardized_botanicals.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def bot_doc() -> Dict[str, Any]:
    with open(os.path.join(_ROOT, "scripts", "data", "botanical_ingredients.json")) as f:
        return json.load(f)


MO2_ENTRIES = [
    {"id": "blue_green_algae", "unii": "49VG1X560X",
     "expected_aliases_subset": ["aphanizomenon flos-aquae"]},
    {"id": "century_plant", "unii": "024852X0VD",
     "expected_aliases_subset": ["agave americana"]},
    {"id": "d_mannose", "unii": "PHA4727WTP",
     "expected_aliases_subset": ["mannose"]},
    {"id": "damiana", "unii": "812R0W1I3K",
     "expected_aliases_subset": ["turnera diffusa"]},
    {"id": "elder_flower", "unii": "07V4DX094T",
     "expected_aliases_subset": ["sambucus nigra flos"]},
    {"id": "galdieria", "unii": "2E5CL9KYZ8",
     "expected_aliases_subset": ["galdieria sulphuraria"]},
    {"id": "grapefruit_seed", "unii": "598D944HOL",
     "expected_aliases_subset": ["citrus paradisi"]},
]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", MO2_ENTRIES, ids=[e["id"] for e in MO2_ENTRIES])
def test_entry_removed_from_standardized_botanicals(std_doc, entry):
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    assert not e, (
        f"std entry '{entry['id']}' must be REMOVED after MO-2. Found: {e}"
    )


@pytest.mark.parametrize("entry", MO2_ENTRIES, ids=[e["id"] for e in MO2_ENTRIES])
def test_entry_present_in_botanical_ingredients(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert e, f"bot entry '{entry['id']}' missing after MO-2."


@pytest.mark.parametrize("entry", MO2_ENTRIES, ids=[e["id"] for e in MO2_ENTRIES])
def test_entry_preserves_unii(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("external_ids") or {}).get("unii") == entry["unii"], (
        f"bot entry '{entry['id']}' must carry UNII '{entry['unii']}'. "
        f"Got: {e.get('external_ids')}"
    )


@pytest.mark.parametrize("entry", MO2_ENTRIES, ids=[e["id"] for e in MO2_ENTRIES])
def test_entry_preserves_aliases(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    aliases = _lc(e.get("aliases", []))
    for required in entry["expected_aliases_subset"]:
        assert required in aliases, (
            f"bot entry '{entry['id']}' must preserve alias '{required}'. "
            f"Got: {e.get('aliases')}"
        )


@pytest.mark.parametrize("entry", MO2_ENTRIES, ids=[e["id"] for e in MO2_ENTRIES])
def test_entry_carries_no_bonus(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    attrs = e.get("attributes") or {}
    assert attrs.get("bonus_eligible") is False
    for v6_field in ("standardization_basis", "marker_compounds", "bonus_rationale"):
        assert v6_field not in e, (
            f"bot entry '{entry['id']}' must not carry v6 contract field "
            f"'{v6_field}'. Got: {v6_field}={e.get(v6_field)!r}"
        )


def test_mo2_net_count_delta(std_doc, bot_doc):
    """MO-1 → 234/493. MO-2 → 227/500."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_actual <= 227, f"std count {std_actual} > 227"
    assert bot_actual >= 500, f"bot count {bot_actual} < 500"


def test_total_entries_invariant(std_doc, bot_doc):
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_doc["_metadata"]["total_entries"] == std_actual
    assert bot_doc["_metadata"]["total_entries"] == bot_actual
