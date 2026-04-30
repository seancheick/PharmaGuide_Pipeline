#!/usr/bin/env python3
"""
Phase 4b — harmful_additives.json category canonicalization contract.

Per CLINICIAN_REVIEW.md Section 2A: 21 distinct category values collapsed
to 12 canonical safety-taxonomy values + 3 transitional V1 holdouts (Phase 4c
migration targets).

Catches any reintroduction of the retired category names.
"""

import json
from pathlib import Path
import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"

# Clinician-locked canonical set
CANONICAL_V1_CATEGORIES = {
    # Phase 4b stable values
    "excipient", "preservative", "emulsifier",
    "colorant_artificial", "colorant_natural",
    "sweetener_artificial", "sweetener_natural", "sweetener_sugar_alcohol",
    "filler", "contaminant", "processing_aid", "phosphate",
}

PHASE_4C_TRANSITIONAL = {
    "mineral_compound",     # Cupric Sulfate → actives
    "nutrient_synthetic",   # Synthetic vitamins → actives
    "stimulant_laxative",   # Senna → actives
}

ALLOWED = CANONICAL_V1_CATEGORIES | PHASE_4C_TRANSITIONAL

RETIRED_VALUES = {
    "artificial_color",         # collapsed → colorant_artificial
    "fat_oil",                  # → excipient (carrier_oil in functional_roles)
    "flavor",                   # → excipient (flavor_* in functional_roles)
    "preservative_antioxidant", # → preservative (antioxidant in functional_roles)
    "sweetener",                # → sweetener_natural (per-entry resolved)
    "colorant",                 # → colorant_natural / excipient per-entry
}


@pytest.fixture(scope="module")
def entries():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["harmful_additives"]


def test_no_retired_category_values(entries):
    """No entry should still carry one of the renamed-away category values."""
    bad = [(e.get("id"), e.get("category"))
           for e in entries
           if e.get("category") in RETIRED_VALUES]
    assert not bad, (
        f"{len(bad)} entries still carry retired category values "
        f"(should have been renamed in Phase 4b): {bad[:5]}"
    )


def test_all_categories_in_allowed_set(entries):
    """Every category value must be in CANONICAL or PHASE_4C_TRANSITIONAL."""
    bad = [(e.get("id"), e.get("category"))
           for e in entries
           if e.get("category") not in ALLOWED]
    assert not bad, (
        f"{len(bad)} entries with non-allowed category: {bad[:5]}\n"
        f"Allowed: {sorted(ALLOWED)}"
    )


def test_specific_high_visibility_renames(entries):
    """Spot-check: specific clinician-flagged renames landed correctly."""
    by_id = {e["id"]: e for e in entries}
    expected = {
        "ADD_ALUMINUM_LAKE_GENERIC": "colorant_artificial",  # was artificial_color
        "ADD_CANOLA_OIL":            "excipient",            # was fat_oil
        "ADD_CORN_OIL":              "excipient",            # was fat_oil
        "ADD_BHA":                   "preservative",         # was preservative_antioxidant
        "ADD_BHT":                   "preservative",         # was preservative_antioxidant
        "ADD_TBHQ":                  "preservative",         # was preservative_antioxidant
        "ADD_CANE_SUGAR":            "sweetener_natural",    # was sweetener
        "ADD_CANE_MOLASSES":         "sweetener_natural",    # was sweetener
        "ADD_HFCS":                  "sweetener_natural",    # was sweetener
        "ADD_IRON_OXIDE":            "colorant_natural",     # was colorant (per-id override)
        "ADD_CANDURIN_SILVER":       "excipient",            # was colorant (per-id override)
        "ADD_VANILLIN":              "excipient",            # was flavor
        "ADD_MSG":                   "excipient",            # was flavor
    }
    bad = [(eid, exp, by_id[eid].get("category"))
           for eid, exp in expected.items()
           if by_id[eid].get("category") != exp]
    assert not bad, f"specific rename failures: {bad}"


def test_canonical_count_within_target(entries):
    """Phase 4b target: ≤15 distinct values (12 canonical + 3 transitional)."""
    distinct = {e.get("category") for e in entries if e.get("category")}
    assert len(distinct) <= 15, (
        f"too many distinct category values ({len(distinct)}); "
        f"clinician target is 12 canonical + 3 transitional. "
        f"Got: {sorted(distinct)}"
    )
