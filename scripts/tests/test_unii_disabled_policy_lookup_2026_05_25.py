#!/usr/bin/env python3
"""Regression coverage for disabled policy entries in UNII/exact lookups.

P0 finding 2026-05-25: `BANNED_ADD_SYNTHETIC_FOOD_ACIDS` is a disabled
multi-compound policy umbrella, but it still owned exact aliases such as
`fumaric acid` in the normalizer's fast lookup and carried the exact fumaric
acid UNII. That caused UNII `88XHZ13131` to resolve to the policy umbrella
instead of the concrete other-ingredient record.
"""

import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


def _load_banned_entry(entry_id: str) -> dict:
    data = json.loads((REPO_ROOT / "scripts/data/banned_recalled_ingredients.json").read_text())
    for entry in data["ingredients"]:
        if entry.get("id") == entry_id:
            return entry
    raise AssertionError(f"missing banned entry {entry_id}")


def _normalizer() -> EnhancedDSLDNormalizer:
    logging.getLogger("enhanced_normalizer").setLevel(logging.ERROR)
    return EnhancedDSLDNormalizer()


def test_disabled_synthetic_food_acids_policy_does_not_carry_exact_fumaric_unii():
    entry = _load_banned_entry("BANNED_ADD_SYNTHETIC_FOOD_ACIDS")

    assert entry["match_mode"] == "disabled"
    assert entry["entity_type"] == "class"
    assert (entry.get("external_ids") or {}).get("unii") is None
    assert "no exact unii" in entry.get("unii_note", "").lower()


def test_disabled_synthetic_food_acids_policy_does_not_own_exact_alias_lookup():
    normalizer = _normalizer()
    payload = normalizer._fast_exact_lookup.get(normalizer.matcher.preprocess_text("fumaric acid"))

    assert payload is not None
    assert payload.get("type") != "banned"
    assert payload.get("standard_name") == "Fumaric Acid"


def test_fumaric_acid_unii_resolves_to_concrete_record_not_policy():
    normalizer = _normalizer()
    payload = normalizer._unii_to_payload_lookup.get("88XHZ13131")

    assert payload is not None
    assert payload.get("type") != "banned"
    assert payload.get("standard_name") == "Fumaric Acid"
    assert payload.get("priority") > 1
