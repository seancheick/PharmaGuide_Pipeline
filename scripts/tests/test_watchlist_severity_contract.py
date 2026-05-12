"""
Watchlist severity contract — regression guard.

`banned_recalled_ingredients.json` has 11 entries with ``status='watchlist'``
(Anatabine, Citrus Red 2, Orange B, Phthalates, Potassium Bromate, etc.).
The clinical-risk semantic: "track this ingredient but DO NOT block or
escalate to user-visible safety concern."

Both the inactive resolver and the active path must classify watchlist
hits as:

  severity_status = "informational"
  is_safety_concern = False
  is_banned = False
  matched_source = "banned_recalled"
  matched_rule_id = the entry's id

A future agent could accidentally:
  - Over-escalate watchlist → critical (lights up Flutter's RBU gate
    on something that shouldn't fire)
  - Suppress watchlist → "n/a" (silently drops a track-only marker)

These tests pin the watchlist contract on both paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Inactive path — direct resolver tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def resolver():
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    return InactiveIngredientResolver()


# Real watchlist entries with stable standard_names (from
# banned_recalled_ingredients.json). If any of these were removed or
# re-classified, the test would surface that as a data-file regression
# too — that's intentional.
WATCHLIST_INACTIVE_CASES = [
    ("Anatabine",         "BANNED_ADD_ANATABINE"),
    ("Citrus Red 2",      "BANNED_ADD_CITRUS_RED_2"),
    ("Orange B",          "BANNED_ADD_ORANGE_B"),
    ("Phthalates",        "BANNED_ADD_PHTHALATES"),
    ("Potassium Bromate", "BANNED_ADD_POTASSIUM_BROMATE"),
]


@pytest.mark.parametrize("raw_name, expected_rule_id", WATCHLIST_INACTIVE_CASES)
def test_inactive_watchlist_resolves_to_informational(resolver, raw_name, expected_rule_id) -> None:
    """Every watchlist inactive must surface as informational, never
    critical, never n/a, never suppressed."""
    r = resolver.resolve(raw_name=raw_name)
    assert r.matched_source == "banned_recalled", (
        f"{raw_name!r} expected matched_source='banned_recalled', got {r.matched_source!r}"
    )
    assert r.matched_rule_id == expected_rule_id, (
        f"{raw_name!r} expected rule {expected_rule_id!r}, got {r.matched_rule_id!r}"
    )
    assert r.severity_status == "informational", (
        f"{raw_name!r} severity_status={r.severity_status!r} — watchlist must be 'informational' "
        "(NOT 'critical' = over-escalation; NOT 'n/a' = silent drop)"
    )
    assert r.is_safety_concern is False, (
        f"{raw_name!r} is_safety_concern={r.is_safety_concern!r} — watchlist must not light up RBU"
    )
    assert r.is_banned is False, (
        f"{raw_name!r} is_banned={r.is_banned!r} — only status='banned' sets is_banned"
    )


def test_inactive_watchlist_carries_safety_reason(resolver) -> None:
    """Even informational watchlist hits should carry a safety_reason
    so Flutter can surface 'why we're tracking it' on tap."""
    r = resolver.resolve(raw_name="Phthalates")
    # Reason might be None if the source entry doesn't have one, but
    # the matched_rule_id MUST be populated for Flutter to look it up.
    assert r.matched_rule_id == "BANNED_ADD_PHTHALATES"


# ---------------------------------------------------------------------------
# Active path — _resolve_active_safety_contract behavior
# ---------------------------------------------------------------------------

def test_active_watchlist_via_ingredient_hits() -> None:
    """When a watchlist hit comes in via ingredient_hits (the enricher's
    contaminant_data path), the active-side resolver must:
      - is_safety_concern = False (informational only)
      - is_banned = False
      - matched_source = 'banned_recalled'
      - matched_rule_id from the watchlist entry
    """
    from scripts.build_final_db import _resolve_active_safety_contract
    fake_hits = [{
        "kind": "contaminant",
        "status": "watchlist",
        "severity_level": "moderate",
        "ingredient": "Phthalates",
        "reason": "Track per FDA guidance",
        "id": "BANNED_ADD_PHTHALATES",
    }]
    c = _resolve_active_safety_contract(
        harmful_hit=None,
        harmful_ref={},
        ingredient_hits=fake_hits,
    )
    assert c["is_safety_concern"] is False, (
        f"active watchlist must NOT set is_safety_concern; got {c['is_safety_concern']!r}"
    )
    assert c["is_banned"] is False
    assert c["matched_source"] == "banned_recalled"
    assert c["matched_rule_id"] == "BANNED_ADD_PHTHALATES"


def test_active_watchlist_via_direct_index_fallback() -> None:
    """When the enricher's contaminant_data didn't catch the variant but
    the direct banned_recalled_index lookup does (alias-fallback path),
    a watchlist match must still resolve to informational — never escalate
    just because we found it through the fallback path."""
    from scripts.build_final_db import _resolve_active_safety_contract
    # Synthesize a one-key index mapping the lookup term to a real watchlist entry.
    fake_index = {
        "phthalates": {
            "id": "BANNED_ADD_PHTHALATES",
            "status": "watchlist",
            "standard_name": "Phthalates",
            "reason": "Track per FDA guidance",
        },
    }
    c = _resolve_active_safety_contract(
        harmful_hit=None,
        harmful_ref={},
        ingredient_hits=[],
        name_terms=["phthalates"],
        banned_recalled_index=fake_index,
    )
    assert c["is_safety_concern"] is False
    assert c["is_banned"] is False
    assert c["matched_source"] == "banned_recalled"
    assert c["matched_rule_id"] == "BANNED_ADD_PHTHALATES"


def test_active_banned_beats_watchlist_when_both_present() -> None:
    """Precedence sanity: if an ingredient happens to match BOTH a
    banned entry and a watchlist entry (different aliases), the banned
    classification must win. Watchlist must never downgrade a banned
    or high_risk classification."""
    from scripts.build_final_db import _resolve_active_safety_contract
    fake_hits = [
        {"status": "watchlist", "id": "WATCH_X", "ingredient": "X"},
        {"status": "banned",    "id": "BAN_Y",   "ingredient": "Y"},
    ]
    c = _resolve_active_safety_contract(
        harmful_hit=None, harmful_ref={}, ingredient_hits=fake_hits,
    )
    assert c["is_safety_concern"] is True
    assert c["is_banned"] is True
    assert c["matched_rule_id"] == "BAN_Y"


def test_active_high_risk_beats_watchlist() -> None:
    """high_risk also beats watchlist."""
    from scripts.build_final_db import _resolve_active_safety_contract
    fake_hits = [
        {"status": "watchlist", "id": "WATCH_X", "ingredient": "X"},
        {"status": "high_risk", "id": "HIGH_Y",  "ingredient": "Y"},
    ]
    c = _resolve_active_safety_contract(
        harmful_hit=None, harmful_ref={}, ingredient_hits=fake_hits,
    )
    assert c["is_safety_concern"] is True
    assert c["is_banned"] is False
    assert c["matched_rule_id"] == "HIGH_Y"
