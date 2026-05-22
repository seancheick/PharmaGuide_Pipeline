"""MO-6: final move-out batch — closes the 89-entry NO-marker queue.

8 special-case entries that needed individual handling:

  barley_grass    UNII 86507VZR9K   already in std; clean move
  cinnamon        UNII 5S29HWU6QB   (generic cinnamon); separate from
                                    bot.cinnamon_bark (Cassia bark)
                                    and bot.ceylon_cinnamon (Verum bark)
                                    — moves to its own bot entry as the
                                    generic identity catch-all
  flaxseed        UNII 310OJT00CG   linum usitatissimum WHOLE (NEW UNII)
  linden_flower   UNII CFN6G1F6YK   tilia cordata FLOWER — separate from
                                    bot.linden (tilia genus, broader)
  shilajit        UNII —            mineral exudate, no FDA UNII
  soy_isoflavones UNII 71B37NR06D   isoflavones (not the soybean hull)
  cistanche       UNII 863KM6AO0R   cistanche tubulosa WHOLE (NEW UNII;
                                    other species C. deserticola defers
                                    to future species-split batch)
  organic_gold_standard_potentiating_nutrients   no UNII
                  proprietary BLEND, not a single-ingredient brand;
                  std entry's own notes say "Insufficient public data
                  for standardization markers". Moves to bot as
                  display-only identity catch-all.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

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


MO6_ENTRIES = [
    {"id": "barley_grass",    "unii": "86507VZR9K"},
    {"id": "cinnamon",        "unii": "5S29HWU6QB"},
    {"id": "flaxseed",        "unii": "310OJT00CG"},
    {"id": "linden_flower",   "unii": "CFN6G1F6YK"},
    {"id": "shilajit",        "unii": None},
    {"id": "soy_isoflavones", "unii": "71B37NR06D"},
    {"id": "cistanche",       "unii": "863KM6AO0R"},
    {"id": "organic_gold_standard_potentiating_nutrients", "unii": None},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


@pytest.mark.parametrize("entry", MO6_ENTRIES, ids=[e["id"] for e in MO6_ENTRIES])
def test_entry_removed_from_std(std_doc, entry):
    assert not _find(std_doc.get("standardized_botanicals", []), entry["id"])


@pytest.mark.parametrize("entry", MO6_ENTRIES, ids=[e["id"] for e in MO6_ENTRIES])
def test_entry_in_bot(bot_doc, entry):
    assert _find(bot_doc.get("botanical_ingredients", []), entry["id"])


@pytest.mark.parametrize("entry", MO6_ENTRIES, ids=[e["id"] for e in MO6_ENTRIES])
def test_unii_correct(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    actual = (e.get("external_ids") or {}).get("unii")
    if entry["unii"] is None:
        # shilajit (mineral exudate) and organic_gold_standard
        # (proprietary blend) intentionally have no FDA UNII
        return
    assert actual == entry["unii"], f"{entry['id']} UNII expected {entry['unii']!r}, got {actual!r}"


@pytest.mark.parametrize("entry", MO6_ENTRIES, ids=[e["id"] for e in MO6_ENTRIES])
def test_no_bonus(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("attributes") or {}).get("bonus_eligible") is False


def test_no_marker_queue_drained(std_doc):
    """After MO-6, no entry from the original 89-candidate NO-marker
    queue should remain without v6 contract."""
    # All remaining std entries should have either:
    #   (a) v6 contract (bonus_eligible=True), OR
    #   (b) marker signal (existing markers[] / min_threshold structure)
    no_marker_left = []
    for e in std_doc.get("standardized_botanicals", []):
        # v6 contract present?
        if e.get("bonus_eligible") is True and e.get("standardization_basis"):
            continue
        # Has marker signal (markers field + structured threshold)?
        if e.get("markers") or e.get("min_threshold") or e.get("standardization"):
            continue
        no_marker_left.append(e.get("id"))
    assert not no_marker_left, (
        f"NO-marker entries still in std after MO-6: {no_marker_left}"
    )
