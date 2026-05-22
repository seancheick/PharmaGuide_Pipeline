"""DM-2: second delete-or-merge batch.

7 more std/bot duplicate entries. Includes two tricky cases that
required investigation before merge:

  1. graviola: std had UNII AN924793RM (ANNONA MURICATA WHOLE),
     bot has UNII 5EI0SM9VVE (ANNONA MURICATA FRUIT — also the FDA
     entry for 'soursop'). The common name 'graviola' specifically
     refers to the FRUIT of Annona muricata, so bot's UNII is more
     accurate. Resolution: keep bot's UNII (FRUIT), drop the std
     entry, merge the 'soursop extract' alias.

  2. cranberry: std unique aliases include 'urophenol' — that's a
     chemical CLASS (hydroxyphenols, often referenced as urinary
     metabolites of cranberry polyphenols), NOT a cranberry
     preparation name. Dropping it on merge.

Entries

  catuaba           (no UNII either side — pure delete, no merge)
  cranberry         UNII 0MVO31Q3QS  +4 aliases (drop 'urophenol')
  graviola          (keep bot UNII 5EI0SM9VVE — FRUIT-precise)  +1 alias
  marshmallow_root  UNII TRW2FUF47H  +3 aliases
  mullein           UNII C9TD27U172  +3 aliases
  sarsaparilla      UNII 2H1576D5WG  +3 aliases
  yucca             UNII 08A0YG3VIC  +2 aliases
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


DM2_ENTRIES = [
    {"id": "catuaba", "bot_unii_expected": None, "newly_merged_aliases": []},
    {"id": "cranberry", "bot_unii_expected": "0MVO31Q3QS",
     "newly_merged_aliases": ["american cranberry", "cranberry extract",
                              "cranberry fruit extract", "cranberry juice concentrate"]},
    # graviola: bot UNII is more accurate (FRUIT vs std's WHOLE)
    {"id": "graviola", "bot_unii_expected": "5EI0SM9VVE",
     "newly_merged_aliases": ["soursop extract"]},
    {"id": "marshmallow_root", "bot_unii_expected": "TRW2FUF47H",
     "newly_merged_aliases": ["althaea", "marshmallow root extract"]},
    {"id": "mullein", "bot_unii_expected": "C9TD27U172",
     "newly_merged_aliases": ["mullein extract", "mullein leaf extract"]},
    {"id": "sarsaparilla", "bot_unii_expected": "2H1576D5WG",
     "newly_merged_aliases": ["sarsaparilla extract", "smilax officinalis"]},
    {"id": "yucca", "bot_unii_expected": "08A0YG3VIC",
     "newly_merged_aliases": ["mojave yucca", "yucca root"]},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", DM2_ENTRIES, ids=[e["id"] for e in DM2_ENTRIES])
def test_std_entry_deleted(std_doc, entry):
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    assert not e, f"std entry '{entry['id']}' must be deleted"


@pytest.mark.parametrize("entry", DM2_ENTRIES, ids=[e["id"] for e in DM2_ENTRIES])
def test_bot_entry_preserved(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert e, f"bot entry '{entry['id']}' missing"
    actual_unii = (e.get("external_ids") or {}).get("unii")
    assert actual_unii == entry["bot_unii_expected"], (
        f"bot entry '{entry['id']}' UNII expected {entry['bot_unii_expected']!r}, "
        f"got {actual_unii!r}"
    )


@pytest.mark.parametrize("entry", DM2_ENTRIES, ids=[e["id"] for e in DM2_ENTRIES])
def test_unique_aliases_merged(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    aliases = _lc(e.get("aliases", []))
    for new_alias in entry["newly_merged_aliases"]:
        assert new_alias in aliases, (
            f"bot entry '{entry['id']}' missing merged alias '{new_alias}'. "
            f"Got: {e.get('aliases')}"
        )


def test_urophenol_NOT_merged(bot_doc):
    """Safety: 'urophenol' was a std cranberry alias but it's a
    chemical class (hydroxyphenols), not a cranberry preparation —
    must NOT be merged into bot.cranberry."""
    e = _find(bot_doc.get("botanical_ingredients", []), "cranberry")
    aliases = _lc(e.get("aliases", []))
    assert "urophenol" not in aliases, (
        f"bot.cranberry must not carry the 'urophenol' alias — it's a "
        f"chemical class, not a cranberry preparation. Got: {e.get('aliases')}"
    )


def test_graviola_uses_fruit_unii(bot_doc):
    """graviola refers to the FRUIT of Annona muricata. bot's
    pre-existing UNII 5EI0SM9VVE (ANNONA MURICATA FRUIT) is the
    accurate identity — the std-side UNII AN924793RM (WHOLE) was
    broader and is intentionally NOT promoted."""
    e = _find(bot_doc.get("botanical_ingredients", []), "graviola")
    assert (e.get("external_ids") or {}).get("unii") == "5EI0SM9VVE"


def test_dm2_net_count(std_doc, bot_doc):
    """DM-1 → 206/514. DM-2 → 199/514."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_actual <= 199, f"std {std_actual} > 199"
    assert bot_actual >= 514, f"bot {bot_actual} < 514"


def test_metadata_invariant(std_doc, bot_doc):
    assert std_doc["_metadata"]["total_entries"] == len(std_doc["standardized_botanicals"])
    assert bot_doc["_metadata"]["total_entries"] == len(bot_doc["botanical_ingredients"])
