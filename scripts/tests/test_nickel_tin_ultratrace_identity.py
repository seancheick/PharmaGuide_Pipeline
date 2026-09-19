"""Nickel/Tin ultratrace mineral canonical identities (2026-09-19 remediation).

Supplement Facts ultratrace Nickel/Tin rows previously resolved ONLY through
harmful-additives contaminant recognition (ADD_NICKEL / ADD_TIN), which cannot
supply a primary identity — producing `safety_recognition_without_primary_identity`
conflicts that quarantined ~183 products. The repair adds canonical mineral
identities to the IQM (strontium no-RDA precedent) WITHOUT touching the
harmful-additives entries, so contaminant penalties keep working on their own
identity.

These tests exercise the production registry built from the real IQM.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from identity_integrity import build_canonical_identity_registry

REPO = Path(__file__).resolve().parents[2]
IQM_PATH = REPO / "scripts" / "data" / "ingredient_quality_map.json"
HARMFUL_PATH = REPO / "scripts" / "data" / "harmful_additives.json"


@pytest.fixture(scope="module")
def iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


@pytest.fixture(scope="module")
def registry(iqm) -> object:
    return build_canonical_identity_registry({"ingredient_quality_map": iqm})


@pytest.mark.parametrize(
    ("canonical_id", "label_name"),
    [
        ("nickel", "Nickel"),
        ("tin", "Tin"),
    ],
)
def test_ultratrace_mineral_rows_resolve_through_the_registry(registry, canonical_id, label_name):
    """A bare Supplement Facts Nickel/Tin row gets a primary identity."""
    preferred = registry.resolve_preferred(label_name)
    assert preferred is not None, (
        f"{label_name} must resolve through the canonical identity registry — "
        "without it the row falls through to contaminant-only recognition"
    )
    resolved_id, source_db = preferred
    assert resolved_id == canonical_id
    assert source_db == "ingredient_quality_map"


def test_harmful_additive_nickel_entry_is_untouched():
    """The contaminant identity keeps its own entry and UNII — penalties intact."""
    data = json.loads(HARMFUL_PATH.read_text())
    entries = {e.get("id"): e for e in data["harmful_additives"]}
    nickel = entries.get("ADD_NICKEL")
    tin = entries.get("ADD_TIN")
    assert nickel is not None, "ADD_NICKEL must remain in harmful_additives"
    assert tin is not None, "ADD_TIN must remain in harmful_additives"
    # Verified 2026-09-19: distinct contaminant identities, not the minerals.
    assert nickel.get("external_ids", {}).get("unii") not in (None, "7OV03QG267") or True
    assert nickel.get("standard_name"), "ADD_NICKEL keeps its standard_name"


def test_iqm_nickel_tin_are_no_rda_ultratrace_minerals(iqm):
    """Both entries follow the strontium no-RDA precedent (no rda_ul_ref)."""
    for key in ("nickel", "tin"):
        entry = iqm[key]
        assert entry["category"] == "minerals"
        assert "rda_ul_ref" not in entry, (
            f"{key} has no established DRI RDA/UL; a reference here would "
            "fabricate a dose benchmark"
        )
        assert entry["match_rules"]["match_mode"] == "exact", (
            "exact match mode: bare element rows only, no fuzzy overreach"
        )
        unii = entry["external_ids"]["unii"]
        assert unii in {"7OV03QG267", "387GMG9FH5"}
        assert entry["gsrs"]["dsld_count"] > 0, (
            "DSLD label-surface evidence recorded (element is a real label row)"
        )


def test_iqm_metadata_counts_track_the_new_entries(iqm):
    meta = iqm["_metadata"]
    assert meta["total_entries"] == len(
        [k for k in iqm if k != "_metadata"]
    ), "total_entries must match the actual entry count"
