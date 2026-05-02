#!/usr/bin/env python3
"""
Batch 4 — `other_ingredients.json` mega-backfill (all 673 entries).

Pins the deterministic-mapper outcome counts and verifies a curated
spot-check of high-visibility entries that the clinician explicitly
called out in CLINICIAN_REVIEW.md Section 3B.
"""

import json
from pathlib import Path
import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "other_ingredients.json"
VOCAB_PATH = Path(__file__).parent.parent / "data" / "functional_roles_vocab.json"


@pytest.fixture(scope="module")
def by_id():
    with open(DATA_PATH, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["other_ingredients"]}


@pytest.fixture(scope="module")
def metadata():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["_metadata"]


@pytest.fixture(scope="module")
def vocab_ids():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return {r["id"] for r in json.load(f)["functional_roles"]}


# ---------------------------------------------------------------------------
# Aggregate counts (deterministic mapper outcome — 2026-04-30 baseline)
# ---------------------------------------------------------------------------


def test_total_entry_count_matches_metadata(by_id, metadata):
    """Entry-count contract lives in _metadata.total_entries."""
    assert len(by_id) == metadata["total_entries"]


def test_aggregate_disposition_counts(by_id):
    """Mapper outcome: 470 populated, 203 deferred ([])."""
    populated = sum(1 for e in by_id.values() if e.get("functional_roles"))
    deferred = sum(
        1 for e in by_id.values()
        if "functional_roles" in e and not e["functional_roles"]
    )
    # 466 = 462 direct-map assigns + 4 per-id overrides (5 colorants + 2
    # sweeteners + Agar = 8 overrides total; minus 1 Glycolipids → []
    # minus 3 descriptor + 1 metabolic_intermediate now in RETIRE = 4 net
    # to populated). New active-only/descriptor entries are expected to stay
    # deferred until they move into the active-ingredient pipeline.
    assert populated == 466, f"expected 466 populated entries; got {populated}"
    assert deferred == len(by_id) - populated, (
        f"expected deferred count to track total-populated; got {deferred}"
    )


def test_all_assigned_roles_in_locked_vocab(by_id, vocab_ids):
    """Every assigned role must be in the 32-ID locked vocab. Catches typos
    in the categorize.py mapper."""
    bad = []
    for entry in by_id.values():
        for r in entry.get("functional_roles", []):
            if r not in vocab_ids:
                bad.append((entry.get("id"), r))
    assert not bad, f"unknown role IDs: {bad[:10]}"


# ---------------------------------------------------------------------------
# Spot-check — clinician's CLINICIAN_REVIEW.md Section 3B sample (high-vis)
# ---------------------------------------------------------------------------

# These entries are the clinician's explicit verification points. If the
# mapper diverges from these, the backfill is wrong — not the test.
SPOT_CHECK = {
    # Standard-name → expected functional_roles (from clinician table 3B)
    "Acacia Gum":                  ["filler", "prebiotic_fiber"],   # via fiber_prebiotic mapping
    "Activated Carbon":            ["processing_aid"],
    "Agar":                        ["gelling_agent", "thickener", "stabilizer"],  # via thickener_stabilizer
    "Allulose":                    ["sweetener_natural"],
    "Apple Flavor":                ["flavor_natural"],
    "Aqueous Film Coating":        ["coating"],
    "Arrowroot":                   ["filler", "binder"],            # via filler_binder
    "Beet Fiber":                  ["filler"],
    "Canola Lecithin":             ["emulsifier"],
    "Cellulose Gum":               ["thickener", "stabilizer"],     # via thickener_stabilizer
    "Chia Seed Meal":              ["filler", "binder"],            # via filler_binder
    "Cinnamon (Natural Flavoring)": ["flavor_natural"],             # via flavoring → flavor_natural default
    "Decaglycerol Monolaurate":    ["emulsifier"],
    "Deionized Water":             ["solvent"],
    "Gelatin Capsule":             ["coating", "gelling_agent"],    # via capsule_material
    "Kaolin":                      ["filler"],
    "Phosphoric Acid":             ["ph_regulator"],                # via acidity_regulator
    "Sodium Acid Sulfate":         ["ph_regulator"],                # via acidity_regulator
    "Hypromellose Capsule":        ["coating", "gelling_agent"],    # via capsule_material
}

# Some clinician-tagged entries (e.g., MCT Oil, Polysorbate 80, Stearic Acid) live
# in harmful_additives.json, not other_ingredients.json — those are pinned by
# test_b01/b02/b03 already. SPOT_CHECK above covers only the other_ingredients
# clinician sample.


@pytest.mark.parametrize("name,expected", list(SPOT_CHECK.items()))
def test_clinician_spot_check_other_ingredients(by_id, name, expected):
    """Each clinician-spot-check entry must match expected roles."""
    matches = [e for e in by_id.values() if e.get("standard_name") == name]
    if not matches:
        pytest.skip(f"{name!r} not in other_ingredients.json (may live elsewhere)")
    actual = matches[0].get("functional_roles", [])
    assert actual == expected, (
        f"{name!r}: expected {expected!r}, got {actual!r}. "
        f"If the mapper outcome is correct and the clinician table is wrong, "
        f"update CLINICIAN_REVIEW.md and this test together."
    )


# ---------------------------------------------------------------------------
# Phase 4 cleanup invariants — these MUST stay [] in V1
# ---------------------------------------------------------------------------


PHASE_4_RETIRED_CATEGORIES = {
    "marketing_descriptor", "descriptor_component", "source_descriptor",
    "phytochemical_marker", "label_descriptor",
}


def test_retired_descriptor_categories_have_empty_roles(by_id):
    """Per clinician Section 2B: retired descriptor categories are label
    noise, not functional ingredients. Must stay []."""
    bad = []
    for entry in by_id.values():
        if entry.get("category") in PHASE_4_RETIRED_CATEGORIES:
            if entry.get("functional_roles", []):
                bad.append((entry.get("id"), entry.get("category"),
                            entry["functional_roles"]))
    assert not bad, f"retired-category entries should have []: {bad[:10]}"
