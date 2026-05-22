"""MO-1: first move-out batch from standardized_botanicals.

7 plain-identity herbs with no documented standardization marker
move from standardized_botanicals.json (bonus file) to
botanical_ingredients.json (plain identity, no bonus). Audit context
in scripts/audits/sb_moveout_inventory_20260522/REPORT.md.

Why this batch is "safest first":

  - Zero alias collisions with existing botanical_ingredients entries
  - No existing bot entry with matching latin_name or strong alias
    overlap → clean new-create (no merge ambiguity)
  - Mix of UNII coverage (7/7 have FDA UNIIs set)
  - Mix of categories (herb, seed_fruit) to exercise the move on
    different shapes
  - Mix of alias counts (3-5) — neither too small (stubs) nor too
    large (camu_camu's 15 deferred to its own batch)

Entries

  american_ginseng    UNII 8W75VCV53Q  Panax quinquefolius (adaptogen
                                       category, but no marker
                                       documentation in current entry)
  astaxanthin         UNII 8XPW32PR7I  Carotenoid pigment; no marker %
  bee_pollen          UNII 3729L8MA2C  Bee pollen granules / extract
  black_cohosh        UNII K73E24S6X9  Actaea / Cimicifuga racemosa
  black_musli         UNII 715B59598O  Curculigo orchioides
  blackberry          UNII 8A6OMU3I8L  Rubus fruticosus fruit
  caraway             UNII W2FH8O2BBE  Carum carvi seed

Out of scope

  - astaxanthin_haematococcus_pluvialis (separate std entry with
    BRANDED aliases — BioAstin, AstaReal, Zanthin — needs
    PROMOTE_V6_BRANDED review, NOT a simple move)
  - The 45 remaining MOVE candidates (queued for MO-2..MO-7 batches)
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


MO1_ENTRIES = [
    {
        "id": "american_ginseng",
        "unii": "8W75VCV53Q",
        "expected_aliases_subset": ["panax quinquefolius", "american ginseng root extract"],
    },
    {
        "id": "astaxanthin",
        "unii": "8XPW32PR7I",
        "expected_aliases_subset": ["astaxanthin extract", "natural astaxanthin"],
    },
    {
        "id": "bee_pollen",
        "unii": "3729L8MA2C",
        "expected_aliases_subset": ["bee pollen extract", "flower pollen"],
    },
    {
        "id": "black_cohosh",
        "unii": "K73E24S6X9",
        "expected_aliases_subset": ["actaea racemosa", "cimicifuga racemosa"],
    },
    {
        "id": "black_musli",
        "unii": "715B59598O",
        "expected_aliases_subset": ["curculigo orchioides", "kali musli"],
    },
    {
        "id": "blackberry",
        "unii": "8A6OMU3I8L",
        "expected_aliases_subset": ["rubus fruticosus", "blackberry fruit extract"],
    },
    {
        "id": "caraway",
        "unii": "W2FH8O2BBE",
        "expected_aliases_subset": ["carum carvi", "caraway seed"],
    },
]


def _find(entries: List[Dict[str, Any]], eid: str) -> Dict[str, Any]:
    for e in entries:
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _lc(values: List[str]) -> List[str]:
    return [(v or "").strip().lower() for v in (values or [])]


@pytest.mark.parametrize("entry", MO1_ENTRIES, ids=[e["id"] for e in MO1_ENTRIES])
def test_entry_removed_from_standardized_botanicals(std_doc, entry):
    """After MO-1, the entry must not exist in standardized_botanicals
    anymore — it has been relocated to botanical_ingredients (plain
    identity, no bonus pathway)."""
    e = _find(std_doc.get("standardized_botanicals", []), entry["id"])
    assert not e, (
        f"std entry '{entry['id']}' must be REMOVED after MO-1. "
        f"Found: {e}"
    )


@pytest.mark.parametrize("entry", MO1_ENTRIES, ids=[e["id"] for e in MO1_ENTRIES])
def test_entry_present_in_botanical_ingredients(bot_doc, entry):
    """The entry must exist in botanical_ingredients post-move with
    the same id."""
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert e, (
        f"bot entry '{entry['id']}' missing after MO-1. The move must "
        f"create a new botanical_ingredients entry, not just delete "
        f"the std entry."
    )


@pytest.mark.parametrize("entry", MO1_ENTRIES, ids=[e["id"] for e in MO1_ENTRIES])
def test_entry_preserves_unii(bot_doc, entry):
    """UNII must be preserved through the move — losing it would
    break the matcher's UNII-first resolution path."""
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    assert (e.get("external_ids") or {}).get("unii") == entry["unii"], (
        f"bot entry '{entry['id']}' must carry UNII '{entry['unii']}' "
        f"(verified via FDA UNII cache). Got: {e.get('external_ids')}"
    )


@pytest.mark.parametrize("entry", MO1_ENTRIES, ids=[e["id"] for e in MO1_ENTRIES])
def test_entry_preserves_aliases(bot_doc, entry):
    """Critical: alias preservation. The runtime matcher uses
    aliases to canonicalize raw label text. Dropping any alias would
    break identity routing for products that mention the dropped
    phrase."""
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    aliases = _lc(e.get("aliases", []))
    for required in entry["expected_aliases_subset"]:
        assert required in aliases, (
            f"bot entry '{entry['id']}' must preserve alias "
            f"'{required}'. Got: {e.get('aliases')}"
        )


@pytest.mark.parametrize("entry", MO1_ENTRIES, ids=[e["id"] for e in MO1_ENTRIES])
def test_entry_carries_no_bonus_attribute(bot_doc, entry):
    """The move STRIPS bonus eligibility — these entries cannot earn
    A5b because they have no documented standardization marker.
    attributes.bonus_eligible (if present) must be False, and no v6
    contract fields may exist."""
    e = _find(bot_doc.get("botanical_ingredients", []), entry["id"])
    attrs = e.get("attributes") or {}
    if "bonus_eligible" in attrs:
        assert attrs["bonus_eligible"] is False, (
            f"bot entry '{entry['id']}' must not claim bonus_eligible. "
            f"Got: {attrs}"
        )
    # No v6 contract fields on plain-identity entries
    for v6_field in ("bonus_eligible", "standardization_basis",
                     "marker_compounds", "bonus_rationale"):
        if v6_field == "bonus_eligible":
            continue  # handled above
        assert v6_field not in e, (
            f"bot entry '{entry['id']}' must not carry v6 contract "
            f"field '{v6_field}' — only plain identity here. Got: {v6_field}={e.get(v6_field)!r}"
        )


def test_total_entries_invariant(std_doc, bot_doc):
    """Both files' _metadata.total_entries must equal the actual
    array length after MO-1."""
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    assert std_doc["_metadata"]["total_entries"] == std_actual, (
        f"std _metadata.total_entries={std_doc['_metadata']['total_entries']} "
        f"≠ actual={std_actual}"
    )
    assert bot_doc["_metadata"]["total_entries"] == bot_actual, (
        f"bot _metadata.total_entries={bot_doc['_metadata']['total_entries']} "
        f"≠ actual={bot_actual}"
    )


def test_mo1_net_count_delta(std_doc, bot_doc):
    """MO-1 moves exactly 7 entries from std to bot.

    Pre-MO-1 (commit ea8adf34): std=241, bot=486.
    Post-MO-1: std=234, bot=493.
    """
    std_actual = len(std_doc.get("standardized_botanicals", []))
    bot_actual = len(bot_doc.get("botanical_ingredients", []))
    # Lower-bound invariants (additive future batches will lift these)
    assert std_actual <= 234, (
        f"std count {std_actual} > 234 — MO-1 must remove 7 entries. "
        f"Future batches may remove more (assert is upper bound)."
    )
    assert bot_actual >= 493, (
        f"bot count {bot_actual} < 493 — MO-1 must add 7 entries. "
        f"Future batches may add more (assert is lower bound)."
    )
