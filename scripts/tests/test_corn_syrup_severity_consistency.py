#!/usr/bin/env python3
"""Corn-syrup-solids severity consistency (2026-07-04).

ADD_CORN_SYRUP_SOLIDS was `moderate` while every other caloric added sugar
(HFCS, cane sugar, dextrose, fructose) is `low`. Audit of its change_log found
no toxicological basis — the prior high->moderate note explicitly flagged it as a
"sugar filler, not toxicological". Downgraded to `low` for consistency; this test
locks the caloric-sugar tier so the outlier can't silently reappear.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

_ENTRIES = {
    e["id"]: e
    for e in json.loads((SCRIPTS_ROOT / "data" / "harmful_additives.json").read_text())["harmful_additives"]
}

CALORIC_SUGARS = ["ADD_CORN_SYRUP_SOLIDS", "ADD_HFCS", "ADD_CANE_SUGAR", "ADD_DEXTROSE", "ADD_FRUCTOSE"]


def test_corn_syrup_solids_is_low_not_moderate():
    e = _ENTRIES["ADD_CORN_SYRUP_SOLIDS"]
    assert e["severity_level"] == "low", "corn syrup solids is a caloric sugar filler, not a toxicological hazard"
    assert e["category"] == "sweetener_natural"


def test_caloric_added_sugars_share_the_low_tier():
    tiers = {sid: _ENTRIES[sid]["severity_level"] for sid in CALORIC_SUGARS if sid in _ENTRIES}
    assert set(tiers.values()) == {"low"}, f"caloric added sugars must all be low, got {tiers}"
