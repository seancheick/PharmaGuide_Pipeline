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


# ---------------------------------------------------------------------------
# STEP 2: the safety gate collects clean_label_hits WITHOUT touching the
# verdict. A clean-label additive (titanium dioxide coating) must surface a
# hit AND keep the verdict SAFE (no CAUTION). The clean-label lane and the
# safety-verdict lane are independent.
# ---------------------------------------------------------------------------


def test_gate_collects_titanium_dioxide_clean_label_hit() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "Coated tablet with titanium dioxide",
        "inactiveIngredients": [{"name": "titanium dioxide"}],
    }
    result = evaluate_safety_gate(product)
    hits = result.clean_label_hits
    assert hits, "titanium dioxide must surface as a clean-label hit"
    hit = next((h for h in hits if "titanium" in str(h.get("name", "")).lower()), None)
    assert hit is not None, f"no titanium hit in {hits!r}"
    assert hit["tier"] == "elevated"
    assert hit["penalty_base"] == 2.0
    assert hit["role"] == "inactive"
    assert hit.get("consumer_note") and "EU" in hit["consumer_note"]


def test_gate_clean_label_does_not_force_caution() -> None:
    # An excipient_acceptable coating must inform, never force CAUTION.
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "x",
        "inactiveIngredients": [{"name": "titanium dioxide"}],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict != "CAUTION", "clean-label hit must not force CAUTION"
    assert result.short_circuits_scoring is False


def test_gate_no_clean_label_hit_when_absent() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "clean product",
        "inactiveIngredients": [{"name": "microcrystalline cellulose"}],
    }
    result = evaluate_safety_gate(product)
    assert result.clean_label_hits == []


def test_gate_eu_banned_active_still_caution_without_clean_label_hit() -> None:
    # propylparaben (penalize_anyway high_risk, NO clean_label block) → CAUTION,
    # and it is NOT a clean-label hit. The two lanes are independent.
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "x",
        "inactiveIngredients": [{"name": "propylparaben"}],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "CAUTION"
    assert result.clean_label_hits == []
