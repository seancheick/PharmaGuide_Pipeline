"""v3.7.0 calibration — A5b tiered, unit-aware, class-capped standardized bonus.

Locks the new behavior:
  - tier ladder full=4 / near_75=3 / near_50=2 / identity_only=1 / none=0
  - per-class caps so non-botanicals can't earn the full botanical tier
    (branded_form/enzyme_activity <= 3, isolated_compound <= 2)
  - best-qualifying ingredient wins (max, not first-match)
  - legacy backward-compat (has_standardized_botanical flag; pre-tier items)
  - data hygiene: dandelion is not 'mushroom'; non-percent thresholds carry a unit
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from score_supplements import SupplementScorer  # noqa: E402


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


def _a5b(scorer, items, has_flag=False):
    prod = {"formulation_data": {"standardized_botanicals": items}}
    if has_flag:
        prod["has_standardized_botanical"] = True
    return scorer._compute_formulation_bonus(prod)["A5b_standardized_botanical"]


@pytest.mark.parametrize(
    "tier,expected",
    [("full", 4.0), ("near_75", 3.0), ("near_50", 2.0), ("identity_only", 1.0), ("none", 0.0)],
)
def test_tier_ladder_botanical(scorer, tier, expected):
    assert _a5b(scorer, [{"tier": tier, "bonus_class": "botanical_standardization"}]) == expected


@pytest.mark.parametrize(
    "bonus_class,expected",
    [
        ("botanical_standardization", 4.0),
        ("marker_percent", 4.0),
        ("mushroom_fraction", 4.0),
        ("branded_form", 3.0),
        ("branded_extract", 3.0),
        ("enzyme_activity", 3.0),
        ("isolated_compound", 2.0),
    ],
)
def test_class_caps_apply_even_at_full_tier(scorer, bonus_class, expected):
    """A 'full' tier is capped by class — minerals/enzymes/isolated compounds
    cannot collect the full +4 botanical standardization bonus."""
    assert _a5b(scorer, [{"tier": "full", "bonus_class": bonus_class}]) == expected


def test_best_ingredient_wins(scorer):
    items = [
        {"tier": "near_50", "bonus_class": "botanical_standardization"},
        {"tier": "full", "bonus_class": "botanical_standardization"},
    ]
    assert _a5b(scorer, items) == 4.0


def test_legacy_flag_grants_identity_only(scorer):
    assert _a5b(scorer, [], has_flag=True) == 1.0


def test_legacy_pretier_branded_item_derives_full(scorer):
    assert _a5b(scorer, [{"meets_threshold": True, "evidence_source": "branded_form"}]) == 4.0


# --------------------------------------------------------------------------- #
# Data-hygiene contract guards
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def sbot():
    p = SCRIPTS / "data" / "standardized_botanicals.json"
    return {e["id"]: e for e in json.loads(p.read_text())["standardized_botanicals"]}


def test_dandelion_is_not_mushroom(sbot):
    assert sbot["dandelion"]["category"] != "mushroom", (
        "dandelion (Taraxacum officinale) is an herb/root, not a fungus — "
        "miscategory leaks into v4 routing."
    )


@pytest.mark.parametrize("entry_id", ["bromelain", "cranrx"])
def test_non_percent_thresholds_declare_unit(sbot, entry_id):
    """Entries whose min_threshold is NOT a percentage (GDU/g, mg_per_dose)
    must declare standardization_unit so enrich does not compare them as '%'."""
    if entry_id not in sbot:
        pytest.skip(f"{entry_id} not present")
    e = sbot[entry_id]
    if e.get("min_threshold") is not None:
        unit = (e.get("standardization_unit") or "percent").lower()
        assert unit not in ("percent", "%"), (
            f"{entry_id} has a non-percent threshold ({e.get('min_threshold')}) "
            f"and must declare its real standardization_unit."
        )


# --------------------------------------------------------------------------- #
# Phase 5 — newly added classic standardized botanicals (source-verified)
# --------------------------------------------------------------------------- #
_PHASE5_ADDED = [
    ("horse_chestnut", "aescin", 16),
    ("american_ginseng_std", "ginsenosides", 10),
    ("garlic_std", "alliin", 0.3),
]


@pytest.mark.parametrize("entry_id,marker,threshold", _PHASE5_ADDED)
def test_phase5_added_botanicals_present_and_eligible(sbot, entry_id, marker, threshold):
    """Classic standardized botanicals added in v3.7.0 Phase 5 must be present,
    bonus_eligible, carry a pharmacopeial basis, a percent unit, the verified
    threshold, and a threshold_source citation (no fabricated identifiers)."""
    assert entry_id in sbot, f"{entry_id} must be present (was missing)."
    e = sbot[entry_id]
    assert e.get("bonus_eligible") is True
    assert e.get("standardization_basis") == "pharmacopeial_marker"
    assert (e.get("standardization_unit") or "").lower() == "percent"
    assert e.get("min_threshold") == threshold
    assert e.get("threshold_source"), f"{entry_id} must cite a threshold_source."
    hay = " ".join(e.get("markers", []) + e.get("marker_compounds", [])).lower()
    assert marker in hay, f"{entry_id} must list its standardization marker '{marker}'."
