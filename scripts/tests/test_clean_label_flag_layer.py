"""Clean-label flag layer — STEP 1: resolver disposition.

The clean-label layer lets EU-banned / flagged additives INFORM + apply a small
graduated penalty WITHOUT forcing a CAUTION verdict (titanium dioxide as a coating).
Step 1 wires the resolver to read an optional `clean_label` block on a
banned_recalled entry and surface it on the resolution, orthogonally to the safety
contract (the verdict is untouched). Steps 2 (gate collection) + 3 (quality_score
graduated penalty + clean_label_flags_v4 emit) follow per
reports/v4_clean_label_flag_design.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def test_titanium_dioxide_carries_clean_label_disposition() -> None:
    from inactive_ingredient_resolver import InactiveIngredientResolver

    res = InactiveIngredientResolver().resolve("titanium dioxide")
    assert res.is_clean_label_concern is True
    assert res.clean_label_tier == "elevated"
    assert res.clean_label_note and "EU" in res.clean_label_note
    assert res.clean_label_penalty_base == 2.0


def test_clean_label_is_orthogonal_to_safety_contract() -> None:
    # The disposition must not be created out of thin air for non-flagged entries,
    # and must not flip the safety contract for titanium dioxide (its excipient_
    # acceptable policy keeps the gate at "warning only" — no verdict change here).
    from inactive_ingredient_resolver import InactiveIngredientResolver

    r = InactiveIngredientResolver()
    # A banned entry WITHOUT a clean_label block → no clean-label disposition.
    cascara = r.resolve("cascara sagrada")
    assert cascara.is_clean_label_concern is False
    assert cascara.clean_label_tier is None


def test_default_resolution_has_no_clean_label() -> None:
    from inactive_ingredient_resolver import InactiveIngredientResolver

    res = InactiveIngredientResolver().resolve("microcrystalline cellulose")
    assert res.is_clean_label_concern is False
    assert res.clean_label_penalty_base is None
