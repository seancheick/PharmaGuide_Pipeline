"""MO-5: fifth move-out batch.

7 entries (5 with newly-verified FDA UNIIs filled during move,
plus barley_grass + camu_camu which were carried over from earlier
deferrals).

Entries

  african_mango  UNII 6V9H6XWU5P  Irvingia gabonensis (NEW)
  akarkara       UNII E3L74Y262L  Anacyclus pyrethrum (NEW)
  horsetail      UNII 1L0VKZ185E  Equisetum arvense leaf powder (NEW)
  muira_puama    UNII G582QI158H  Ptychopetalum olacoides (NEW)
  rosehip        UNII P5R39F12N2  Rosa canina (NEW)
  lion_s_mane    UNII Y62T8P9AAP  Hericium erinaceus (NEW)
  camu_camu      UNII EAG5BC91EK  Myrciaria dubia whole (NEW) — 15 aliases

For lion_s_mane the std entry has aliases that overlap with bot's
existing lion_s_mane_mushroom and similar entries — handled with
drop-list filtering (mushroom-fruiting-body specifics already
elsewhere).
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


MO5_ENTRIES = [
    {"id": "african_mango", "unii": "6V9H6XWU5P",
     "expected_aliases_subset": ["irvingia gabonensis"]},
    {"id": "akarkara", "unii": "E3L74Y262L",
     "expected_aliases_subset": ["anacyclus pyrethrum"]},
    {"id": "horsetail", "unii": "1L0VKZ185E",
     "expected_aliases_subset": ["equisetum arvense"]},
    {"id": "muira_puama", "unii": "G582QI158H",
     "expected_aliases_subset": ["ptychopetalum olacoides"]},
    {"id": "rosehip", "unii": "P5R39F12N2",
     "expected_aliases_subset": ["rosa canina"]},
    {"id": "lion_s_mane", "unii": "Y62T8P9AAP",
     "expected_aliases_subset": ["hericium erinaceus"]},
    {"id": "camu_camu", "unii": "EAG5BC91EK",
     "expected_aliases_subset": ["myrciaria dubia"]},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", MO5_ENTRIES, ids=[e["id"] for e in MO5_ENTRIES])
def test_entry_removed_from_std(std_doc, entry):
    assert not _find(std_doc.get("standardized_botanicals", []), entry["id"])


@pytest.mark.parametrize("entry", MO5_ENTRIES, ids=[e["id"] for e in MO5_ENTRIES])
def test_entry_in_bot(bot_doc, entry):
    assert _find(bot_doc.get("botanical_ingredients", []), entry["id"])


@pytest.mark.parametrize("entry", MO5_ENTRIES, ids=[e["id"] for e in MO5_ENTRIES])
def test_unii_set(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("external_ids") or {}).get("unii") == entry["unii"]


@pytest.mark.parametrize("entry", MO5_ENTRIES, ids=[e["id"] for e in MO5_ENTRIES])
def test_aliases_preserved(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    aliases = _lc(e.get("aliases", []))
    for required in entry["expected_aliases_subset"]:
        assert required in aliases


@pytest.mark.parametrize("entry", MO5_ENTRIES, ids=[e["id"] for e in MO5_ENTRIES])
def test_no_bonus(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("attributes") or {}).get("bonus_eligible") is False


def test_mo5_net_count(std_doc, bot_doc):
    """DM-3 → 192/514. MO-5 → 185/521."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_actual <= 185
    assert bot_actual >= 521


def test_metadata_invariant(std_doc, bot_doc):
    assert std_doc["_metadata"]["total_entries"] == len(std_doc["standardized_botanicals"])
    assert bot_doc["_metadata"]["total_entries"] == len(bot_doc["botanical_ingredients"])
