"""MO-4: fourth move-out batch.

7 more plain-identity entries. 3 carry UNIIs already; 4 receive
newly-verified FDA UNIIs as part of this batch (baobab, black_sesame,
mallow, polygala — all verified via scripts/data/fda_unii_cache.json).

Entries

  saffron        UNII E849G4X5YJ  Crocus sativus (existing)
  slippery_elm   UNII 63POE2M46Y  Ulmus rubra (existing)
  spinach        UNII 6WO75C6WVB  Spinacia oleracea (existing)
  baobab         UNII D5B40OA634  Adansonia digitata whole (NEW)
  black_sesame   UNII JD6YPE8XLT  Sesamum indicum whole (NEW)
  mallow         UNII I01732476C  Malva sylvestris whole (NEW)
  polygala       UNII F6BP27WG28  Polygala tenuifolia whole (NEW)

Deferred from this batch

  camu_camu (15 aliases — own batch; needs careful per-alias review)
  cistanche (C. tubulosa vs C. deserticola — needs species split)
  flaxseed  (no clean Linum usitatissimum WHOLE UNII; only oil/seed
             husk variants — defer to UNII research batch)
  shilajit  (no FDA UNII — mineral exudate, not strictly botanical;
             defer to triage)
  astazine  (looks like a branded extract — PROMOTE_V6_BRANDED)
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


MO4_ENTRIES = [
    {"id": "saffron", "unii": "E849G4X5YJ",
     "expected_aliases_subset": ["crocus sativus"]},
    {"id": "slippery_elm", "unii": "63POE2M46Y",
     "expected_aliases_subset": ["ulmus rubra"]},
    {"id": "spinach", "unii": "6WO75C6WVB",
     "expected_aliases_subset": ["spinacia oleracea"]},
    {"id": "baobab", "unii": "D5B40OA634",
     "expected_aliases_subset": ["adansonia digitata"]},
    {"id": "black_sesame", "unii": "JD6YPE8XLT",
     "expected_aliases_subset": ["black sesame seed"]},
    {"id": "mallow", "unii": "I01732476C",
     "expected_aliases_subset": ["malva sylvestris"]},
    {"id": "polygala", "unii": "F6BP27WG28",
     "expected_aliases_subset": ["polygala tenuifolia"]},
]


def _find(entries, eid):
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values):
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", MO4_ENTRIES, ids=[e["id"] for e in MO4_ENTRIES])
def test_entry_removed_from_std(std_doc, entry):
    assert not _find(std_doc.get("standardized_botanicals", []), entry["id"])


@pytest.mark.parametrize("entry", MO4_ENTRIES, ids=[e["id"] for e in MO4_ENTRIES])
def test_entry_in_bot(bot_doc, entry):
    assert _find(bot_doc.get("botanical_ingredients", []), entry["id"])


@pytest.mark.parametrize("entry", MO4_ENTRIES, ids=[e["id"] for e in MO4_ENTRIES])
def test_unii_preserved(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("external_ids") or {}).get("unii") == entry["unii"], (
        f"bot entry '{entry['id']}' must carry UNII '{entry['unii']}'. "
        f"Got: {e.get('external_ids')}"
    )


@pytest.mark.parametrize("entry", MO4_ENTRIES, ids=[e["id"] for e in MO4_ENTRIES])
def test_aliases_preserved(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    aliases = _lc(e.get("aliases", []))
    for required in entry["expected_aliases_subset"]:
        assert required in aliases


@pytest.mark.parametrize("entry", MO4_ENTRIES, ids=[e["id"] for e in MO4_ENTRIES])
def test_no_bonus(bot_doc, entry):
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("attributes") or {}).get("bonus_eligible") is False


def test_mo4_net_count(std_doc, bot_doc):
    """MO-3 → 220/507. MO-4 → 213/514."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_actual <= 213
    assert bot_actual >= 514


def test_metadata_invariant(std_doc, bot_doc):
    assert std_doc["_metadata"]["total_entries"] == len(std_doc["standardized_botanicals"])
    assert bot_doc["_metadata"]["total_entries"] == len(bot_doc["botanical_ingredients"])
