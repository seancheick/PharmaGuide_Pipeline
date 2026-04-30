#!/usr/bin/env python3
"""
Batch 1 — `harmful_additives.json` entries 1-40 (alphabetical by id).

Pins the clinician-locked `functional_roles[]` assignments for the first 40
entries of harmful_additives.json (ADD_ACESULFAME_K through ADD_HFCS).

Source of truth:
  - scripts/audits/functional_roles/CLINICIAN_REVIEW.md (Sections 2A, 3A, 4F)
  - scripts/audits/functional_roles/batch_01/research.md (per-entry evidence)

Coverage after batch 1: 31/40 entries with ≥1 role; 9 intentionally deferred
(4 contaminants — clinician-excluded; 2 V1.1-attribute-required; 1 Phase 4
move-to-actives).
"""

import json
import os
from pathlib import Path

import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"
VOCAB_PATH = Path(__file__).parent.parent / "data" / "functional_roles_vocab.json"


@pytest.fixture(scope="module")
def by_id():
    with open(DATA_PATH, encoding="utf-8") as f:
        d = json.load(f)
    return {e["id"]: e for e in d["harmful_additives"]}


@pytest.fixture(scope="module")
def vocab_ids():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        v = json.load(f)
    return {r["id"] for r in v["functional_roles"]}


# ---------------------------------------------------------------------------
# Clinician-locked assignments — exact match required
# ---------------------------------------------------------------------------

EXPECTED_ROLES = {
    # Sweeteners — artificial
    "ADD_ACESULFAME_K":               ["sweetener_artificial"],
    "ADD_ADVANTAME":                  ["sweetener_artificial"],
    "ADD_ASPARTAME":                  ["sweetener_artificial"],
    # Sweeteners — natural / nutritive
    "ADD_CANE_SUGAR":                 ["sweetener_natural"],
    "ADD_CANE_MOLASSES":              ["sweetener_natural", "flavor_natural", "colorant_natural"],
    "ADD_DEXTROSE":                   ["sweetener_natural"],
    "ADD_FRUCTOSE":                   ["sweetener_natural"],
    "ADD_HFCS":                       ["sweetener_natural"],
    "ADD_D_MANNOSE":                  ["sweetener_natural"],
    # Sugar alcohol
    "ADD_ERYTHRITOL":                 ["sweetener_sugar_alcohol"],
    # Colorants — artificial
    "ADD_BLUE1":                      ["colorant_artificial"],
    "ADD_BLUE2":                      ["colorant_artificial"],
    "ADD_GREEN3":                     ["colorant_artificial"],
    "ADD_ALUMINUM_LAKE_GENERIC":      ["colorant_artificial"],
    # Colorants — natural
    "ADD_CARMINE_RED":                ["colorant_natural"],
    # Preservatives + antioxidants (split from preservative_antioxidant)
    "ADD_BHA":                        ["preservative", "antioxidant"],
    "ADD_BHT":                        ["preservative", "antioxidant"],
    "ADD_CALCIUM_DISODIUM_EDTA":      ["preservative", "antioxidant"],
    "ADD_DISODIUM_EDTA":              ["preservative", "antioxidant"],
    # Emulsifiers / multi-role hydrocolloids
    "ADD_CARBOXYMETHYLCELLULOSE":     ["emulsifier", "thickener", "stabilizer"],
    "ADD_CARRAGEENAN":                ["emulsifier", "thickener", "gelling_agent", "stabilizer"],
    "ADD_FATTY_ACID_POLYGLYCEROL_ESTERS": ["emulsifier", "surfactant"],
    # Carrier oils (fat_oil → carrier_oil per clinician)
    "ADD_CANOLA_OIL":                 ["carrier_oil"],
    "ADD_CORN_OIL":                   ["carrier_oil"],
    # Disintegrants
    "ADD_CROSCARMELLOSE_SODIUM":      ["disintegrant"],
    "ADD_CROSPOVIDONE":               ["disintegrant"],
    # Lubricants / flow agents
    "ADD_CALCIUM_LAURATE":            ["lubricant"],
    "ADD_CALCIUM_CITRATE_LAURATE":    ["lubricant"],
    "ADD_CALCIUM_SILICATE":           ["anti_caking_agent", "glidant"],
    "ADD_CALCIUM_ALUMINUM_PHOSPHATE": ["processing_aid", "anti_caking_agent"],
    # Fillers
    "ADD_CASSAVA_DEXTRIN":            ["filler"],
    "ADD_CORN_SYRUP_SOLIDS":          ["filler", "sweetener_natural"],
    # Flavorings
    "ADD_ARTIFICIAL_FLAVORS":         ["flavor_artificial"],
}

# Entries that MUST stay empty per clinician decisions
DEFERRED_EMPTY = {
    # Contaminants — architectural exclusion (clinician Section 2A)
    "ADD_ACRYLAMIDE":     "contaminant — unintended impurity, not a functional ingredient",
    "ADD_ANTIMONY":       "contaminant — heavy metal",
    "ADD_BISPHENOL_F":    "contaminant — packaging migration",
    "ADD_BISPHENOL_S":    "contaminant — packaging migration",
    # V1.1 attribute layer required for class disambiguation
    "ADD_CARAMEL_COLOR":  "V1.1: needs attributes.caramel_class (i/ii/iii/iv) — Class III/IV carry 4-MEI Prop 65 concern",
    # Per-product source verification
    "ADD_CANDURIN_SILVER": "V1.1: per-product source verification — brand covers multiple formulations",
    # Phase 4 move-to-actives
    "ADD_CUPRIC_SULFATE": "Phase 4: relocates to active-ingredient pipeline (copper source)",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_batch_1_scope_complete(by_id):
    """Every batch 1 entry exists in the data file."""
    in_scope = set(EXPECTED_ROLES) | set(DEFERRED_EMPTY)
    missing = in_scope - set(by_id)
    assert not missing, f"batch 1 entries missing from harmful_additives.json: {missing}"
    assert len(in_scope) == 40, f"batch 1 must define exactly 40 entries; got {len(in_scope)}"


def test_assigned_entries_match_clinician_locked_values(by_id, vocab_ids):
    """Every assignment matches the clinician's locked values exactly. Order
    matters per the table; a wrong-order list fails this test."""
    mismatches = []
    unknown = []
    for entry_id, expected in EXPECTED_ROLES.items():
        actual = by_id[entry_id].get("functional_roles", [])
        if actual != expected:
            mismatches.append((entry_id, expected, actual))
        for r in actual:
            if r not in vocab_ids:
                unknown.append((entry_id, r))
    assert not unknown, f"unknown role IDs (not in locked vocab): {unknown}"
    assert not mismatches, (
        f"{len(mismatches)} entries don't match clinician-locked roles:\n"
        + "\n".join(
            f"  {eid}: expected {exp!r}, got {act!r}"
            for eid, exp, act in mismatches[:10]
        )
    )


def test_deferred_entries_remain_empty(by_id):
    """Contaminants and Phase-4/V1.1-deferred entries MUST stay empty.
    Non-empty here means a backfill mistakenly assigned a role to a
    contaminant (architectural violation) or a deferred entry."""
    violations = []
    for entry_id, reason in DEFERRED_EMPTY.items():
        roles = by_id[entry_id].get("functional_roles", [])
        if roles:
            violations.append((entry_id, roles, reason))
    assert not violations, (
        f"{len(violations)} deferred/contaminant entries have non-empty "
        f"functional_roles[]:\n"
        + "\n".join(
            f"  {eid}: got {roles!r} but should be [] ({reason})"
            for eid, roles, reason in violations
        )
    )


def test_batch_1_coverage_metric(by_id):
    """Batch 1 invariant: 33 entries get ≥1 role, 7 intentionally empty.
    Deferred = 4 contaminants + 2 V1.1-attribute-required (Caramel,
    Candurin) + 1 Phase-4-move-to-actives (Cupric Sulfate)."""
    in_scope = set(EXPECTED_ROLES) | set(DEFERRED_EMPTY)
    populated = sum(
        1 for eid in in_scope
        if by_id[eid].get("functional_roles", [])
    )
    assert populated == 33, (
        f"batch 1 should populate exactly 33/40 entries (7 deferred); "
        f"got {populated}"
    )


def test_no_role_appears_more_than_4_times_in_a_single_entry(by_id):
    """Sanity ceiling — no entry should have more than 4 roles. Catches
    over-assignment from over-eager backfill scripts."""
    over = []
    for entry_id in EXPECTED_ROLES:
        roles = by_id[entry_id].get("functional_roles", [])
        if len(roles) > 4:
            over.append((entry_id, len(roles)))
    assert not over, f"entries with >4 roles (likely over-assigned): {over}"
