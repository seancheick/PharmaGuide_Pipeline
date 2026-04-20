#!/usr/bin/env python3
"""Regression pins for xylitol unmapped resolution."""

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_xylitol_in_harmful_additives():
    """Xylitol must exist in harmful_additives as sweetener_sugar_alcohol."""
    d = json.loads((DATA_DIR / "harmful_additives.json").read_text())
    rows = {e["id"]: e for e in d["harmful_additives"]}

    assert "ADD_XYLITOL" in rows, "Xylitol entry missing from harmful_additives"
    x = rows["ADD_XYLITOL"]
    assert x["standard_name"] == "Xylitol"
    assert x["category"] == "sweetener_sugar_alcohol"
    # Sprint D1.3: sugar alcohols downgraded to severity_level='low' —
    # they deserve a small penalty (quality signal), not the full harmful-
    # additive hammer. Nutrition-Facts-panel rows no longer reach the
    # scorer at all (filtered by _is_nutrition_fact); only formulation-use
    # Xylitol rows land here, and those get the small 'low' penalty.
    assert x["severity_level"] == "low", (
        "D1.3 policy: formulation-use sugar alcohols carry severity_level='low' "
        "so the scorer applies a reduced B1 penalty. See docs/SPRINT_D_ACCURACY_100.md."
    )
    assert x["cui"] == "C0043369"
    ext = x.get("external_ids", {})
    assert ext.get("unii") == "VCQ006KQ1E"
    assert ext.get("cas") == "87-99-0"
    assert "xylitol" in [a.lower() for a in x.get("aliases", [])]


def test_xylitol_in_iqm():
    """Xylitol must exist in IQM for scoring when it appears as active ingredient."""
    d = json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())
    assert "xylitol" in d, "Xylitol entry missing from IQM"
    x = d["xylitol"]
    assert x["standard_name"] == "Xylitol"
    assert x["cui"] == "C0043369"
    ext = x.get("external_ids", {})
    assert ext.get("unii") == "VCQ006KQ1E"


def test_xylitol_in_cross_db_overlap():
    """Xylitol must be in cross-DB overlap allowlist (exists in both IQM and harmful)."""
    d = json.loads((DATA_DIR / "cross_db_overlap_allowlist.json").read_text())
    terms = [e.get("term_normalized", "").lower() for e in d.get("allowed_overlaps", [])]
    assert "xylitol" in terms, "Xylitol missing from cross-DB overlap allowlist"
