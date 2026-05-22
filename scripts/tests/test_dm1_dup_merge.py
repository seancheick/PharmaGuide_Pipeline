"""DM-1: first delete-or-merge batch.

7 entries where the SAME id already exists in both
standardized_botanicals.json and botanical_ingredients.json with
matching UNIIs. The std-side entries are duplicates of bot-side
plain-identity entries with no documented standardization marker
— they should be DELETED from std, with any unique aliases merged
into the existing bot entry.

Pattern (for each entry):
  1. std entry has the same id and UNII as the bot entry
  2. std entry has no marker signal (would not earn A5b bonus)
  3. Some std aliases are unique to std (not yet in bot)
  4. Merge: union std aliases into bot, then DELETE std entry

Entries

  aloe_vera     UNII ZY81Z83H0X   +1 alias to bot
  carrot        UNII L56Z1JK48B   +2 aliases to bot
  chamomile     UNII FGL3685T2X   +4 aliases to bot
  cucumber      UNII YY7C30VXJT   +2 aliases to bot
  fennel        UNII 557II4LLC3   +2 aliases to bot
  kale          UNII 0Y3L4J38H1   +1 alias to bot
  lavender      UNII ZBP1YXW0H8   +0 aliases (pure delete — already merged)

Deferred to DM-2

  catuaba          (no UNII on either side — needs UNII research)
  cranberry        (5 unique aliases — bigger merge)
  graviola         (UNII MISMATCH — std=AN924793RM, bot=5EI0SM9VVE; needs investigation)
  marshmallow_root (3 unique)
  mullein          (3 unique)
  sarsaparilla     (3 unique)
  yucca            (2 unique)
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


DM1_ENTRIES = [
    {"id": "aloe_vera", "unii": "ZY81Z83H0X",
     "newly_merged_aliases": ["aloe vera extract"]},
    {"id": "carrot", "unii": "L56Z1JK48B",
     "newly_merged_aliases": ["carrot extract", "carrot powder"]},
    {"id": "chamomile", "unii": "FGL3685T2X",
     "newly_merged_aliases": ["chamomile extract", "matricaria recutita"]},
    {"id": "cucumber", "unii": "YY7C30VXJT",
     "newly_merged_aliases": ["cucumber extract", "cucumber seed extract"]},
    {"id": "fennel", "unii": "557II4LLC3",
     "newly_merged_aliases": ["fennel extract", "sweet fennel"]},
    {"id": "kale", "unii": "0Y3L4J38H1",
     "newly_merged_aliases": ["curly kale"]},
    {"id": "lavender", "unii": "ZBP1YXW0H8",
     "newly_merged_aliases": []},  # pure delete
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", DM1_ENTRIES, ids=[e["id"] for e in DM1_ENTRIES])
def test_std_entry_deleted(std_doc, entry):
    """The duplicate std-side entry must be deleted."""
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    assert not e, (
        f"std entry '{entry['id']}' must be deleted in DM-1 "
        f"(duplicate of bot.{entry['id']} with matching UNII). Found: {e}"
    )


@pytest.mark.parametrize("entry", DM1_ENTRIES, ids=[e["id"] for e in DM1_ENTRIES])
def test_bot_entry_preserved(bot_doc, entry):
    """The bot-side entry must still exist (it owned the plain identity
    all along) and retain its UNII."""
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert e, f"bot entry '{entry['id']}' missing"
    assert (e.get("external_ids") or {}).get("unii") == entry["unii"], (
        f"bot entry '{entry['id']}' UNII must remain '{entry['unii']}'. "
        f"Got: {e.get('external_ids')}"
    )


@pytest.mark.parametrize("entry", DM1_ENTRIES, ids=[e["id"] for e in DM1_ENTRIES])
def test_unique_std_aliases_merged_into_bot(bot_doc, entry):
    """Aliases that were unique to std must now appear in bot."""
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    bot_aliases = _lc(e.get("aliases", []))
    for new_alias in entry["newly_merged_aliases"]:
        assert new_alias in bot_aliases, (
            f"bot entry '{entry['id']}' missing newly-merged alias "
            f"'{new_alias}'. Got: {e.get('aliases')}"
        )


def test_dm1_net_count(std_doc, bot_doc):
    """MO-4 → 213/514. DM-1 → 206/514 (bot unchanged; std loses 7)."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_actual <= 206, f"std {std_actual} > 206"
    # bot count unchanged by DM (it's pure delete + alias merge)
    assert bot_actual >= 514, f"bot {bot_actual} < 514"


def test_metadata_invariant(std_doc, bot_doc):
    assert std_doc["_metadata"]["total_entries"] == len(std_doc["standardized_botanicals"])
    assert bot_doc["_metadata"]["total_entries"] == len(bot_doc["botanical_ingredients"])
