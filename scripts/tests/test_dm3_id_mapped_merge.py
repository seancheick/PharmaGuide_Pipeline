"""DM-3: id-mapped merge batch.

7 cases where std had a BROADER id and bot has a MORE-SPECIFIC id
for the same plant (same UNII). The broader std entry must be
deleted; its unique aliases merge into the more-specific bot entry
under the bot's id. The std id is dropped — products mapping by
alias still resolve correctly via the bot entry.

Mappings (std broader → bot more-specific):

  alfalfa            → alfalfa_leaf       (UNII HY3L927V6M match)
  garlic             → garlic_bulb        (UNII V1V998DC17 match)
  kelp               → kelp_powder        (UNII 168S4EO8YJ match)
  oregano            → oregano_herb       (UNII 0E5AT8T16U match)
  psyllium           → psyllium_husk      (UNII 0SHO53407G match)
  yellow_dock        → yellow_dock_root   (UNII S9T422Q956 match)
  wheatgrass         → wheatgrass_powder  (bot UNII was None; FILLED with 3C3Y389JBU from std)

Deferred (UNII mismatches need species investigation)

  cinnamon → cinnamon_bark: std=5S29HWU6QB (generic CINNAMON), bot=WS4CQ062KM
    (CINNAMOMUM CASSIA BARK). Different species/preparations.
  linden_flower → linden: std=CFN6G1F6YK, bot=W5E5UB44GD. Possibly
    different Tilia species (cordata vs platyphyllos).
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


DM3_MAPPINGS = [
    {"std_id": "alfalfa", "bot_id": "alfalfa_leaf", "unii": "HY3L927V6M",
     "merged_aliases_sample": ["alfalfa extract"]},
    {"std_id": "garlic", "bot_id": "garlic_bulb", "unii": "V1V998DC17",
     "merged_aliases_sample": ["aged garlic extract", "kyolic"]},
    {"std_id": "kelp", "bot_id": "kelp_powder", "unii": "168S4EO8YJ",
     "merged_aliases_sample": ["laminaria"]},
    {"std_id": "oregano", "bot_id": "oregano_herb", "unii": "0E5AT8T16U",
     "merged_aliases_sample": ["oregano oil", "wild oregano"]},
    {"std_id": "psyllium", "bot_id": "psyllium_husk", "unii": "0SHO53407G",
     "merged_aliases_sample": ["psyllium husk"]},
    {"std_id": "yellow_dock", "bot_id": "yellow_dock_root", "unii": "S9T422Q956",
     "merged_aliases_sample": ["curly dock", "rumex"]},
    {"std_id": "wheatgrass", "bot_id": "wheatgrass_powder", "unii": "3C3Y389JBU",
     "merged_aliases_sample": ["wheatgrass powder", "wheat grass juice"]},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("m", DM3_MAPPINGS, ids=[m["std_id"] for m in DM3_MAPPINGS])
def test_std_broader_id_deleted(std_doc, m):
    e = _find(std_doc.get("standardized_botanicals", []), m["std_id"])
    assert not e, f"std.{m['std_id']} must be deleted (broader → use more-specific bot.{m['bot_id']})"


@pytest.mark.parametrize("m", DM3_MAPPINGS, ids=[m["std_id"] for m in DM3_MAPPINGS])
def test_bot_specific_preserved(bot_doc, m):
    e = _find(bot_doc.get("botanical_ingredients", []), m["bot_id"])
    assert e, f"bot.{m['bot_id']} missing"
    actual_unii = (e.get("external_ids") or {}).get("unii")
    assert actual_unii == m["unii"], (
        f"bot.{m['bot_id']} UNII expected {m['unii']!r}, got {actual_unii!r}"
    )


@pytest.mark.parametrize("m", DM3_MAPPINGS, ids=[m["std_id"] for m in DM3_MAPPINGS])
def test_aliases_merged_to_specific(bot_doc, m):
    e = _find(bot_doc.get("botanical_ingredients", []), m["bot_id"])
    aliases = _lc(e.get("aliases", []))
    for a in m["merged_aliases_sample"]:
        assert a in aliases, (
            f"bot.{m['bot_id']} missing merged alias '{a}' from std.{m['std_id']}. "
            f"Got: {e.get('aliases')}"
        )


def test_wheatgrass_unii_filled(bot_doc):
    """wheatgrass_powder previously had no UNII; the merge should
    fill it with the std-side UNII 3C3Y389JBU."""
    e = _find(bot_doc.get("botanical_ingredients", []), "wheatgrass_powder")
    assert (e.get("external_ids") or {}).get("unii") == "3C3Y389JBU"


def test_dm3_net_count(std_doc, bot_doc):
    """DM-2 → 199/514. DM-3 → 192/514."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_actual <= 192
    assert bot_actual >= 514


def test_metadata_invariant(std_doc, bot_doc):
    assert std_doc["_metadata"]["total_entries"] == len(std_doc["standardized_botanicals"])
    assert bot_doc["_metadata"]["total_entries"] == len(bot_doc["botanical_ingredients"])
