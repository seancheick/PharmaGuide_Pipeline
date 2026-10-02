"""LEDGER Q63 (Sean 2026-10-02): "synthetic food acids" is not a safety concept.

Citric, fumaric and adipic acid are the same molecules whatever their source,
and no evidence shows a safety difference. The record stays only as a
redirect target: it may not name a real ingredient, warn, or score.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def _entry() -> dict:
    data = json.loads((DATA / "banned_recalled_ingredients.json").read_text())
    return next(e for e in data["ingredients"] if e["id"] == "BANNED_ADD_SYNTHETIC_FOOD_ACIDS")


def test_the_record_names_no_real_ingredient():
    entry = _entry()
    assert entry["match_mode"] == "disabled"
    names = {a.lower() for a in entry["aliases"]}
    for chemical in ("fumaric acid", "adipic acid", "e297", "e355", "synthetic citric acid"):
        assert chemical not in names


def test_the_copy_does_not_imply_synthetic_acids_are_less_safe():
    entry = _entry()
    copy = f"{entry['safety_warning']} {entry['safety_warning_one_liner']}".lower()
    assert "avoid" not in copy and "concern" not in entry["safety_warning"].lower()
    assert entry["legal_status_enum"] == "lawful"


def test_the_redirect_target_still_exists():
    redirects = json.loads((DATA / "id_redirects.json").read_text())
    assert "ADD_SYNTHETIC_FOOD_ACIDS" in json.dumps(redirects)
    assert _entry()["id"] == "BANNED_ADD_SYNTHETIC_FOOD_ACIDS"
